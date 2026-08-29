from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from collections.abc import Iterator
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import get_settings
from app.debate_schemas import (
    DebateCancelRequest,
    DebateChallengeRequest,
    DebateCreateRequest,
    DebateExplanationRequest,
    DebateMessageRecord,
    DebateMutationResponse,
    DebateSessionDetail,
)
from app.domain.debate import DebateSession
from app.domain.explanations import ExplanationResult
from app.domain.events import DebateEvent
from app.providers.current_factors import build_current_factor_registry
from app.providers.debate_factory import build_debate_streaming_turn_provider
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.explanation_factory import (
    ExplanationProviderConfigurationError,
    build_explanation_provider,
)
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateQueueRepository,
    DebateRepositoryError,
)
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ExaminationRequest,
    ExaminationResponse,
    EvidenceItem,
    MarketQuote,
    MacroObservation,
    MacroSeries,
    MacroSeriesContext,
    PricePoint,
    PriceHistoryPoint,
    Stock,
    StockBundle,
    StockCoverage,
    TechnicalIndicators,
    WatchlistRequest,
    WatchlistResponse,
)
from app.services.analysis import AnalysisService
from app.services.analysis_context import build_analysis_context
from app.services.auth import AuthContext, SupabaseAuthVerifier, extract_bearer_token
from app.services.cache import build_cache_backend
from app.services.debate_admission import (
    ActiveDebateExists,
    DebateAdmissionPolicy,
    DebateAdmissionReservation,
    DebateIdempotencyGuard,
    DebateIdempotencyLockBusy,
    DebateIdempotencyReservation,
    DebateRateLimitExceeded,
)
from app.services.debate_snapshot_cache import StandardDebateSnapshotCache
from app.services.debate_orchestrator import DebateOrchestrationError
from app.services.debate_event_broker import (
    DebateEventCursorExpired,
    InMemoryDebateEventBroker,
    format_debate_sse,
)
from app.services.debate_preview import DebatePreviewService
from app.services.debate_worker import DebateWorker
from app.services.demo_store import DemoStore
from app.services.explanation import (
    ExplanationNotFound,
    ExplanationProviderError,
    ExplanationService,
    ExplanationValidationError,
)
from app.services.explanation_admission import (
    ExplanationAdmissionPolicy,
    ExplanationRateLimitExceeded,
)
from app.services.indicators import calculate_indicators
from app.services.model_provider import ProviderError
from app.services.market_data import FinnhubQuoteClient, MarketDataError, QuoteCache
from app.services.rag import retrieve_evidence
from app.services.response_cache import (
    JsonResponseCache,
    stock_bundle_cache_key,
    stock_search_cache_key,
)
from app.services.supabase_store import RepositoryError, SupabaseStore

settings = get_settings()
logger = logging.getLogger(__name__)
if settings.persistence_mode.lower().strip() == "supabase":
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Supabase persistence requires SUPABASE_URL and SUPABASE_ANON_KEY")
    store = SupabaseStore(
        settings.supabase_url,
        settings.supabase_anon_key,
        price_stale_after_days=settings.price_stale_after_days,
    )
else:
    store = DemoStore()
analysis_service = AnalysisService(store)
debate_event_broker = InMemoryDebateEventBroker()
debate_streaming_turn_provider = (
    build_debate_streaming_turn_provider(settings)
    if settings.debate_queue_enabled
    else None
)
debate_preview_service: DebatePreviewService | None
if settings.persistence_mode.lower().strip() == "supabase":
    if settings.supabase_url and settings.supabase_secret_key:
        debate_repository = SupabaseDebateRepository(
            settings.supabase_url,
            settings.supabase_secret_key,
        )
        debate_provider = DeterministicDebateProvider()
        debate_preview_service = DebatePreviewService(
            debate_repository,
            debate_provider,
            debate_provider,
            streaming_turn_provider=debate_streaming_turn_provider,
            event_publisher=debate_event_broker,
        )
    else:
        debate_preview_service = None
else:
    debate_repository = InMemoryDebateRepository()
    debate_provider = DeterministicDebateProvider()
    debate_preview_service = DebatePreviewService(
        debate_repository,
        debate_provider,
        debate_provider,
        streaming_turn_provider=debate_streaming_turn_provider,
        event_publisher=debate_event_broker,
    )
quote_cache = (
    QuoteCache(FinnhubQuoteClient(settings.finnhub_api_key))
    if settings.finnhub_api_key and settings.environment != "test"
    else None
)
cache_backend = build_cache_backend(
    enabled=settings.redis_enabled,
    redis_url=settings.redis_url,
    connect_timeout_seconds=settings.redis_connect_timeout_seconds,
    socket_timeout_seconds=settings.redis_socket_timeout_seconds,
)
response_cache = JsonResponseCache(cache_backend, enabled=settings.redis_enabled)
debate_snapshot_cache = StandardDebateSnapshotCache(response_cache)
debate_admission_policy = DebateAdmissionPolicy(
    cache_backend,
    rate_limit=settings.debate_rate_limit_per_window,
    rate_window_seconds=settings.debate_rate_limit_window_seconds,
    active_ttl_seconds=settings.debate_active_ttl_seconds,
)
debate_idempotency_guard = DebateIdempotencyGuard(
    cache_backend,
    ttl_seconds=settings.debate_idempotency_lock_ttl_seconds,
)
explanation_admission_policy = ExplanationAdmissionPolicy(
    cache_backend,
    rate_limit=settings.explanation_rate_limit_per_window,
    rate_window_seconds=settings.explanation_rate_limit_window_seconds,
)


def build_configured_debate_worker() -> DebateWorker:
    if debate_preview_service is None:
        raise RuntimeError("Debate Queue Worker persistence is not configured")
    repository = debate_preview_service.repository
    if not isinstance(repository, DebateQueueRepository):
        raise RuntimeError("Debate Queue transport is not configured")
    return DebateWorker(
        repository,
        repository,
        debate_preview_service.orchestrator,
        visibility_timeout_seconds=settings.debate_worker_visibility_timeout_seconds,
    )


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    if not settings.debate_queue_enabled:
        yield
        return

    stop_event = asyncio.Event()
    worker = build_configured_debate_worker()
    tasks = [
        asyncio.create_task(
            worker.run_forever(
                stop_event,
                poll_seconds=settings.debate_worker_poll_seconds,
            ),
            name=f"debate-worker-{index + 1}",
        )
        for index in range(settings.debate_worker_concurrency)
    ]
    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Educational stock-signal explanations using deterministic demo data.",
    lifespan=app_lifespan,
)


@app.exception_handler(RepositoryError)
def repository_error_handler(request: Request, exc: RepositoryError) -> JSONResponse:
    logger.warning("Repository request failed: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Persistence service unavailable"},
    )


@app.exception_handler(DebateConcurrencyError)
def debate_concurrency_error_handler(
    request: Request,
    exc: DebateConcurrencyError,
) -> JSONResponse:
    logger.warning("Debate request conflicted: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Debate state changed; refresh the session and try again"},
    )


@app.exception_handler(DebateRepositoryError)
def debate_repository_error_handler(
    request: Request,
    exc: DebateRepositoryError,
) -> JSONResponse:
    logger.warning("Debate persistence request failed: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Debate persistence service unavailable"},
    )


def current_auth(
    authorization: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if settings.auth_mode.lower().strip() == "demo":
        return AuthContext(
            user_id=x_user_id or settings.demo_user_id,
            access_token=None,
        )
    access_token = extract_bearer_token(authorization)
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
        )
    verifier = SupabaseAuthVerifier(settings.supabase_url, settings.supabase_anon_key)
    return verifier.verify(access_token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment, "provider": settings.analysis_provider}


@app.get("/health/cache")
def cache_health(
    probe: bool = Query(default=False),
) -> dict[str, object]:
    health = cache_backend.health(probe=probe)
    return {
        "status": "degraded" if health.mode == "degraded" else "ok",
        "mode": health.mode,
        "redis_configured": health.redis_configured,
        "redis_reachable": health.redis_reachable,
        "degraded_operations": health.degraded_operations,
    }


def _require_stock(ticker: str) -> Stock:
    stock = store.get_stock(ticker)
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return Stock.model_validate(stock)


def _coverage(stock: Stock) -> StockCoverage:
    has_price_data = stock.coverage_status in {
        "price_cached",
        "evidence_ready",
        "debate_ready",
    }
    has_evidence = stock.coverage_status in {"evidence_ready", "debate_ready"}
    return StockCoverage(
        ticker=stock.ticker,
        coverage_status=stock.coverage_status,
        has_price_data=has_price_data,
        has_evidence=has_evidence,
        can_debate=stock.coverage_status == "debate_ready",
    )


def require_debate_workflow_v2() -> None:
    if not settings.debate_workflow_v2:
        raise HTTPException(status_code=404, detail="Debate V2 is not enabled")
    if debate_preview_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Debate V2 persistence is not configured",
        )


def _debate_user_id(auth: AuthContext) -> UUID:
    if settings.auth_mode.lower().strip() == "demo":
        return uuid5(NAMESPACE_URL, f"ai-bull-vs-bear:user:{auth.user_id}")
    try:
        return UUID(auth.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authenticated user") from exc


def _debate_context(ticker: str, question: str | None):
    prices = store.get_prices(ticker)
    if not prices:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debate requires a cached price snapshot",
        )
    as_of = str(prices[-1]["date"])
    macro_context: list[dict[str, object]] = []
    try:
        for raw_series in store.get_macro_series():
            series = MacroSeries.model_validate(raw_series)
            candidates = [
                MacroObservation.model_validate(row)
                for row in store.get_macro_observations(series.code, limit=10)
                if str(row.get("observation_date", "")) <= as_of
            ]
            if not candidates:
                continue
            latest = max(candidates, key=lambda item: item.observation_date)
            macro_context.append(
                {
                    "code": series.code,
                    "name": series.name,
                    "source": series.source,
                    "unit": series.unit,
                    "observation_date": latest.observation_date,
                    "value": latest.value,
                    "retrieved_at": latest.retrieved_at,
                    "metadata": latest.metadata,
                }
            )
    except Exception:
        logger.warning("Optional macro snapshot unavailable for Debate %s", ticker)
    context = build_analysis_context(
        ticker,
        as_of=as_of,
        prices=prices,
        evidence=store.get_evidence(ticker),
        macro_context=macro_context,
        question=question,
    )
    registry = build_current_factor_registry()
    cached_snapshot = debate_snapshot_cache.get_or_collect(
        context,
        registry.collect,
        provider_contract=registry.snapshot_contract,
    )
    return context, cached_snapshot.snapshot, cached_snapshot.status


def _debate_session_or_404(session_id: UUID, user_id: UUID) -> DebateSession:
    assert debate_preview_service is not None
    session = debate_preview_service.repository.get_session(session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Debate session not found")
    return session


def _debate_message_records(
    session: DebateSession,
) -> tuple[DebateMessageRecord, ...]:
    assert debate_preview_service is not None
    messages = debate_preview_service.repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )
    return tuple(
        DebateMessageRecord(
            message=message,
            citations=debate_preview_service.repository.list_message_evidence(
                message.id,
                session.user_id,
            ),
        )
        for message in messages
    )


def _debate_detail(session: DebateSession) -> DebateSessionDetail:
    assert debate_preview_service is not None
    return DebateSessionDetail(
        session=session,
        messages=_debate_message_records(session),
        job=debate_preview_service.repository.get_active_job(
            session.id,
            session.user_id,
        ),
        execution_mode=(
            "queued" if settings.debate_queue_enabled else "synchronous_preview"
        ),
    )


def _debate_event_cursor(
    after_sequence: int | None,
    last_event_id: str | None,
) -> int:
    if after_sequence is not None:
        return after_sequence
    if not last_event_id:
        return 0
    try:
        cursor = int(last_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be a sequence") from exc
    if cursor < 0:
        raise HTTPException(status_code=400, detail="Last-Event-ID cannot be negative")
    return cursor


def _debate_sse_frames(
    session: DebateSession,
    *,
    after_sequence: int,
    initial_events: tuple[DebateEvent, ...] = (),
    heartbeat_seconds: float = 15.0,
) -> Iterator[str]:
    cursor = after_sequence
    pending = initial_events
    terminal_types = {
        "session.awaiting_user",
        "session.completed",
        "session.cancelled",
        "session.failed",
    }
    while True:
        events = pending
        pending = ()
        if not events:
            try:
                events = debate_event_broker.wait_for_events(
                    session.id,
                    after_sequence=cursor,
                    timeout=heartbeat_seconds,
                )
            except DebateEventCursorExpired:
                return
        if events:
            for event in events:
                cursor = event.sequence
                yield format_debate_sse(event)
                if event.type in terminal_types:
                    return
            continue
        assert debate_preview_service is not None
        current = debate_preview_service.repository.get_session(session.id, session.user_id)
        if current is None or current.status in {
            "awaiting_user",
            "completed",
            "cancelled",
            "failed",
        }:
            return
        yield format_debate_sse(debate_event_broker.heartbeat(session.id))


@app.get("/stocks", response_model=list[Stock])
def list_stocks(
    response: Response,
    q: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=20, ge=1, le=25),
) -> list[Stock]:
    cache_key = stock_search_cache_key(q, limit)
    cached = response_cache.read(cache_key)
    if isinstance(cached.value, list):
        try:
            stocks = [Stock.model_validate(stock) for stock in cached.value]
            response.headers["X-Cache-Status"] = cached.status
            return stocks
        except ValueError:
            pass
    stocks = [Stock.model_validate(stock) for stock in store.list_stocks(q, limit)]
    response_cache.write(
        cache_key,
        [stock.model_dump(mode="json") for stock in stocks],
        ttl_seconds=1800,
    )
    response.headers["X-Cache-Status"] = response_cache.response_status(cached.status)
    return stocks


@app.get("/stocks/{ticker}", response_model=Stock)
def get_stock(ticker: str) -> Stock:
    return _require_stock(ticker)


@app.get("/stocks/{ticker}/coverage", response_model=StockCoverage)
def get_stock_coverage(ticker: str) -> StockCoverage:
    return _coverage(_require_stock(ticker))


@app.get("/stocks/{ticker}/prices", response_model=list[PricePoint])
def get_prices(ticker: str) -> list[PricePoint]:
    if not _coverage(_require_stock(ticker)).has_price_data:
        return []
    return [PricePoint.model_validate(point) for point in store.get_prices(ticker)]


@app.get("/stocks/{ticker}/price-history", response_model=list[PriceHistoryPoint])
def get_price_history(
    ticker: str,
    frequency: str = Query(default="weekly", pattern="^weekly$"),
) -> list[PriceHistoryPoint]:
    if not _coverage(_require_stock(ticker)).has_price_data:
        return []
    return [
        PriceHistoryPoint.model_validate(point)
        for point in store.get_price_history(ticker, frequency)
    ]


@app.get("/stocks/{ticker}/quote", response_model=MarketQuote | None)
def get_quote(ticker: str) -> MarketQuote | None:
    if not _coverage(_require_stock(ticker)).has_price_data:
        return None
    if quote_cache is None:
        return None
    try:
        return MarketQuote.model_validate(quote_cache.get(ticker))
    except MarketDataError:
        logger.warning("Latest quote lookup failed for %s", ticker.upper())
        return None


def _stock_bundle_core(ticker: str) -> StockBundle:
    stock = _require_stock(ticker)
    if not _coverage(stock).has_price_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock bundle is unavailable for this catalog-only stock",
        )
    prices = [PricePoint.model_validate(point) for point in store.get_prices(ticker)]
    weekly_history = [
        PriceHistoryPoint.model_validate(point)
        for point in store.get_price_history(ticker, "weekly")
    ]
    indicators = TechnicalIndicators.model_validate(
        calculate_indicators(ticker.upper(), [point.model_dump() for point in prices])
    )
    evidence = [
        EvidenceItem.model_validate(item)
        for item in store.get_evidence(ticker)
    ] if _coverage(stock).has_evidence else []
    macro_context = get_macro_context(limit=60) if ticker.upper() == "AAPL" else []
    return StockBundle(
        stock=stock,
        prices=prices,
        weekly_history=weekly_history,
        quote=None,
        indicators=indicators,
        evidence=evidence,
        macro_context=macro_context,
    )


@app.get("/stocks/{ticker}/bundle", response_model=StockBundle)
def get_stock_bundle(ticker: str, response: Response) -> StockBundle:
    stock = _require_stock(ticker)
    if not _coverage(stock).has_price_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock bundle is unavailable for this catalog-only stock",
        )
    cache_key = stock_bundle_cache_key(stock.ticker)
    cached = response_cache.read(cache_key)
    core: StockBundle | None = None
    if isinstance(cached.value, dict):
        try:
            core = StockBundle.model_validate(cached.value)
        except ValueError:
            core = None
    if core is None:
        core = _stock_bundle_core(stock.ticker)
        response_cache.write(
            cache_key,
            core.model_dump(mode="json"),
            ttl_seconds=300,
        )
    response.headers["X-Cache-Status"] = response_cache.response_status(cached.status)
    return core.model_copy(update={"quote": get_quote(stock.ticker)})


@app.get("/macro/series", response_model=list[MacroSeries])
def get_macro_series() -> list[MacroSeries]:
    return [MacroSeries.model_validate(item) for item in store.get_macro_series()]


@app.get("/macro/series/{series_code}", response_model=list[MacroObservation])
def get_macro_observations(
    series_code: str,
    limit: int = Query(default=400, ge=1, le=1000),
) -> list[MacroObservation]:
    return [
        MacroObservation.model_validate(item)
        for item in store.get_macro_observations(series_code, limit)
    ]


@app.get("/macro/context", response_model=list[MacroSeriesContext])
def get_macro_context(
    limit: int = Query(default=60, ge=2, le=400),
) -> list[MacroSeriesContext]:
    return [
        MacroSeriesContext(
            series=MacroSeries.model_validate(item),
            observations=[
                MacroObservation.model_validate(observation)
                for observation in store.get_macro_observations(str(item["code"]), limit)
            ],
        )
        for item in store.get_macro_series()
    ]


@app.get("/stocks/{ticker}/indicators", response_model=TechnicalIndicators)
def get_indicators(ticker: str) -> TechnicalIndicators:
    if not _coverage(_require_stock(ticker)).has_price_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technical indicators are unavailable for this catalog-only stock",
        )
    return TechnicalIndicators.model_validate(calculate_indicators(ticker.upper(), store.get_prices(ticker)))


@app.get("/stocks/{ticker}/evidence", response_model=list[EvidenceItem])
def get_evidence(
    ticker: str,
    q: str | None = Query(default=None, max_length=300),
) -> list[EvidenceItem]:
    if not _coverage(_require_stock(ticker)).has_evidence:
        return []
    documents = store.get_evidence(ticker)
    if q:
        search_evidence = getattr(store, "search_evidence", None)
        documents = search_evidence(ticker, q) if callable(search_evidence) else retrieve_evidence(documents, q)
    return [EvidenceItem.model_validate(item) for item in documents]


@app.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(auth: Annotated[AuthContext, Depends(current_auth)]) -> WatchlistResponse:
    return WatchlistResponse(
        user_id=auth.user_id,
        tickers=store.get_watchlist(auth.user_id, auth.access_token),
    )


@app.post("/watchlist", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist(
    item: WatchlistRequest,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> WatchlistResponse:
    ticker = item.ticker.upper()
    if store.get_stock(ticker) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return WatchlistResponse(
        user_id=auth.user_id,
        tickers=store.add_watchlist(auth.user_id, ticker, auth.access_token),
    )


@app.delete("/watchlist/{ticker}", response_model=WatchlistResponse)
def remove_watchlist(
    ticker: str,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> WatchlistResponse:
    return WatchlistResponse(
        user_id=auth.user_id,
        tickers=store.remove_watchlist(auth.user_id, ticker, auth.access_token),
    )


@app.post(
    "/debates",
    response_model=DebateMutationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=settings.debate_workflow_v2,
)
def create_debate(
    request: DebateCreateRequest,
    response: Response,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> DebateMutationResponse:
    stock = _require_stock(request.ticker)
    if not _coverage(stock).can_debate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bull vs Bear is available only for Debate-ready stocks",
        )
    assert debate_preview_service is not None
    user_id = _debate_user_id(auth)
    try:
        stock_id = store.get_stock_record_id(stock.ticker, auth.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Stock not found") from exc

    idempotency_reservation: DebateIdempotencyReservation | None = None
    reservation: DebateAdmissionReservation | None = None
    confirmed_reservation = False
    try:
        if settings.debate_queue_enabled and request.idempotency_key:
            idempotency_reservation = debate_idempotency_guard.acquire(
                user_id,
                request.idempotency_key,
            )

        idempotent_retry = (
            settings.debate_queue_enabled
            and debate_preview_service.has_queued_round_one_admission(
                user_id,
                request.idempotency_key,
            )
        )
        if not idempotent_retry:
            reservation = debate_admission_policy.reserve(
                user_id,
                debate_preview_service.repository,
            )
            response.headers["X-RateLimit-Limit"] = str(reservation.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(reservation.remaining)

        execution_mode = "synchronous_preview"
        context, factor_snapshot, cache_status = _debate_context(
            stock.ticker,
            request.question,
        )
        response.headers["X-Cache-Status"] = cache_status
        if settings.debate_queue_enabled:
            session, job = debate_preview_service.create_queued_round_one(
                user_id=user_id,
                stock_id=stock_id,
                ticker=stock.ticker,
                opening_side=request.opening_side,
                question=request.question,
                idempotency_key=request.idempotency_key,
                analysis_context=context,
                factor_snapshot=factor_snapshot,
            )
            response.status_code = status.HTTP_202_ACCEPTED
            execution_mode = "queued"
        else:
            session, job = debate_preview_service.create_and_execute_round_one(
                user_id=user_id,
                stock_id=stock_id,
                ticker=stock.ticker,
                opening_side=request.opening_side,
                question=request.question,
                analysis_context=context,
                factor_snapshot=factor_snapshot,
            )
        if reservation is not None:
            debate_admission_policy.confirm(reservation, session)
            confirmed_reservation = True
        detail = _debate_detail(session)
        return DebateMutationResponse(
            session=detail.session,
            messages=detail.messages,
            job=detail.job,
            job_id=job.id,
            execution_mode=execution_mode,
        )
    except DebateIdempotencyLockBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An equivalent Debate request is being admitted; retry shortly",
            headers={"Retry-After": "1"},
        ) from exc
    except ActiveDebateExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish or cancel the active Debate before starting another",
        ) from exc
    except DebateRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Debate generation limit reached; retry later",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Stock not found") from exc
    except DebateOrchestrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Debate preview execution failed",
        ) from exc
    finally:
        if reservation is not None and not confirmed_reservation:
            debate_admission_policy.release(reservation)
        if idempotency_reservation is not None:
            debate_idempotency_guard.release(idempotency_reservation)


@app.get(
    "/debates",
    response_model=list[DebateSession],
    include_in_schema=settings.debate_workflow_v2,
)
def list_debates(
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DebateSession]:
    assert debate_preview_service is not None
    return debate_preview_service.repository.list_sessions(
        _debate_user_id(auth),
        limit=limit,
    )


@app.get(
    "/debates/{session_id}",
    response_model=DebateSessionDetail,
    include_in_schema=settings.debate_workflow_v2,
)
def get_debate(
    session_id: UUID,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> DebateSessionDetail:
    return _debate_detail(_debate_session_or_404(session_id, _debate_user_id(auth)))


@app.get(
    "/debates/{session_id}/messages",
    response_model=list[DebateMessageRecord],
    include_in_schema=settings.debate_workflow_v2,
)
def get_debate_messages(
    session_id: UUID,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> list[DebateMessageRecord]:
    session = _debate_session_or_404(session_id, _debate_user_id(auth))
    return list(_debate_message_records(session))


@app.post(
    "/debates/{session_id}/explanations",
    response_model=ExplanationResult,
    include_in_schema=settings.debate_workflow_v2,
)
def explain_debate(
    session_id: UUID,
    request: DebateExplanationRequest,
    response: Response,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> ExplanationResult:
    assert debate_preview_service is not None
    user_id = _debate_user_id(auth)
    try:
        admission = explanation_admission_policy.admit(user_id)
    except ExplanationRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Explanation request limit reached; retry later",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    response.headers["X-RateLimit-Limit"] = str(admission.rate_limit)
    response.headers["X-RateLimit-Remaining"] = str(admission.remaining)
    try:
        provider = build_explanation_provider(settings)
    except ExplanationProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Explanation service is temporarily unavailable",
        ) from exc
    service = ExplanationService(debate_preview_service.repository, provider)
    try:
        return service.explain(
            session_id=session_id,
            user_id=user_id,
            source_message_id=request.message_id,
            selected_text=request.selected_text,
            question=request.question,
        )
    except ExplanationNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debate explanation source was not found",
        ) from exc
    except ExplanationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explanation request is not valid for this Debate message",
        ) from exc
    except ExplanationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Explanation service is temporarily unavailable",
        ) from exc


@app.get(
    "/debates/{session_id}/events",
    include_in_schema=settings.debate_workflow_v2,
)
def stream_debate_events(
    session_id: UUID,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
    after_sequence: int | None = Query(default=None, ge=0),
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    session = _debate_session_or_404(session_id, _debate_user_id(auth))
    cursor = _debate_event_cursor(after_sequence, last_event_id)
    try:
        initial_events = debate_event_broker.replay(
            session.id,
            after_sequence=cursor,
        )
    except DebateEventCursorExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Event cursor expired; reload canonical Debate messages before reconnecting"
            ),
            headers={
                "X-Debate-Latest-Sequence": str(
                    debate_event_broker.latest_sequence(session.id)
                )
            },
        ) from exc
    return StreamingResponse(
        _debate_sse_frames(
            session,
            after_sequence=cursor,
            initial_events=initial_events,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/debates/{session_id}/cancel",
    response_model=DebateSessionDetail,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=settings.debate_workflow_v2,
)
def cancel_debate(
    session_id: UUID,
    request: DebateCancelRequest,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> DebateSessionDetail:
    assert debate_preview_service is not None
    user_id = _debate_user_id(auth)
    _debate_session_or_404(session_id, user_id)
    try:
        cancelled = debate_preview_service.orchestrator.request_cancellation(
            session_id,
            user_id,
            request.generation_id,
        )
    except DebateOrchestrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _debate_detail(cancelled)


@app.post(
    "/debates/{session_id}/interventions",
    response_model=DebateMutationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=settings.debate_workflow_v2,
)
def challenge_debate(
    session_id: UUID,
    request: DebateChallengeRequest,
    response: Response,
    _feature: Annotated[None, Depends(require_debate_workflow_v2)],
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> DebateMutationResponse:
    assert debate_preview_service is not None
    session = _debate_session_or_404(session_id, _debate_user_id(auth))
    if session.status != "awaiting_user" and not (
        settings.debate_queue_enabled and request.idempotency_key
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debate session is not awaiting a user challenge",
        )
    target = next(
        (
            record.message
            for record in _debate_message_records(session)
            if record.message.id == request.selected_message_id
        ),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge target is not in the active Debate branch",
        )
    if request.selected_text not in target.content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected text is not present in the target message",
        )
    try:
        if settings.debate_queue_enabled:
            completed, job = debate_preview_service.create_queued_round_two(
                session=session,
                selected_message_id=request.selected_message_id,
                selected_text=request.selected_text,
                question=request.question,
                idempotency_key=request.idempotency_key,
            )
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            completed, job = debate_preview_service.submit_challenge_and_execute_round_two(
                session=session,
                selected_message_id=request.selected_message_id,
                selected_text=request.selected_text,
                question=request.question,
            )
    except DebateOrchestrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debate challenge could not be applied",
        ) from exc
    detail = _debate_detail(completed)
    return DebateMutationResponse(
        session=detail.session,
        messages=detail.messages,
        job=detail.job,
        job_id=job.id,
        execution_mode=detail.execution_mode,
    )


@app.post("/analysis/{ticker}", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
def create_analysis(
    ticker: str,
    request: AnalysisRequest,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> AnalysisResponse:
    if not _coverage(_require_stock(ticker)).can_debate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bull vs Bear is available only for Debate-ready stocks",
        )
    try:
        return analysis_service.create(
            ticker,
            request.question,
            auth.user_id,
            auth.access_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/analysis", response_model=list[AnalysisResponse])
def list_analysis(auth: Annotated[AuthContext, Depends(current_auth)]) -> list[AnalysisResponse]:
    return [
        item
        for item in store.list_analyses(auth.user_id, auth.access_token)
        if isinstance(item, AnalysisResponse)
    ]


@app.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: str,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> AnalysisResponse:
    response = analysis_service.get(analysis_id, auth.user_id, auth.access_token)
    if response is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return response


@app.get("/analysis/{analysis_id}/trace")
def get_trace(
    analysis_id: str,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> list[dict[str, object]]:
    response = analysis_service.get(analysis_id, auth.user_id, auth.access_token)
    if response is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return [step.model_dump() for step in response.trace]


@app.get("/analysis/{analysis_id}/tokens")
def get_tokens(
    analysis_id: str,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> dict[str, object]:
    response = analysis_service.get(analysis_id, auth.user_id, auth.access_token)
    if response is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return response.token_usage.model_dump()


@app.post("/claims/{claim_id}/examine", response_model=ExaminationResponse)
def examine_claim(
    claim_id: str,
    request: ExaminationRequest,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> ExaminationResponse:
    try:
        return analysis_service.examine(
            claim_id,
            request.question_type,
            auth.user_id,
            auth.access_token,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def root(request: Request) -> dict[str, str]:
    return {"name": settings.app_name, "docs": str(request.base_url) + "docs"}


# Keep CORS outside FastAPI's server-error middleware so unexpected errors
# still return the allowed-origin header instead of a browser-only CORS error.
app = CORSMiddleware(
    app=app,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Cache-Status",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "Retry-After",
    ],
)
