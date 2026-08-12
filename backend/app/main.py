from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ExaminationRequest,
    ExaminationResponse,
    EvidenceItem,
    PricePoint,
    Stock,
    TechnicalIndicators,
    WatchlistRequest,
    WatchlistResponse,
)
from app.services.analysis import AnalysisService
from app.services.auth import AuthContext, SupabaseAuthVerifier, extract_bearer_token
from app.services.demo_store import DemoStore
from app.services.indicators import calculate_indicators
from app.services.model_provider import ProviderError
from app.services.rag import retrieve_evidence
from app.services.supabase_store import RepositoryError, SupabaseStore

settings = get_settings()
if settings.persistence_mode.lower().strip() == "supabase":
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Supabase persistence requires SUPABASE_URL and SUPABASE_ANON_KEY")
    store = SupabaseStore(settings.supabase_url, settings.supabase_anon_key)
else:
    store = DemoStore()
analysis_service = AnalysisService(store)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Educational stock-signal explanations using deterministic demo data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RepositoryError)
def repository_error_handler(request: Request, exc: RepositoryError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Persistence service unavailable"},
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
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
        )
    access_token = extract_bearer_token(authorization)
    verifier = SupabaseAuthVerifier(settings.supabase_url, settings.supabase_anon_key)
    return verifier.verify(access_token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment, "provider": settings.analysis_provider}


@app.get("/stocks", response_model=list[Stock])
def list_stocks(q: str | None = Query(default=None, max_length=40)) -> list[Stock]:
    return [Stock.model_validate(stock) for stock in store.list_stocks(q)]


@app.get("/stocks/{ticker}", response_model=Stock)
def get_stock(ticker: str) -> Stock:
    stock = store.get_stock(ticker)
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return Stock.model_validate(stock)


@app.get("/stocks/{ticker}/prices", response_model=list[PricePoint])
def get_prices(ticker: str) -> list[PricePoint]:
    if store.get_stock(ticker) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return [PricePoint.model_validate(point) for point in store.get_prices(ticker)]


@app.get("/stocks/{ticker}/indicators", response_model=TechnicalIndicators)
def get_indicators(ticker: str) -> TechnicalIndicators:
    if store.get_stock(ticker) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return TechnicalIndicators.model_validate(calculate_indicators(ticker.upper(), store.get_prices(ticker)))


@app.get("/stocks/{ticker}/evidence", response_model=list[EvidenceItem])
def get_evidence(
    ticker: str,
    q: str | None = Query(default=None, max_length=300),
) -> list[EvidenceItem]:
    if store.get_stock(ticker) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    documents = store.get_evidence(ticker)
    if q:
        documents = retrieve_evidence(documents, q)
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


@app.post("/analysis/{ticker}", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
def create_analysis(
    ticker: str,
    request: AnalysisRequest,
    auth: Annotated[AuthContext, Depends(current_auth)],
) -> AnalysisResponse:
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
