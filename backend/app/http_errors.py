"""Translate service failures into stable, credential-free API responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.repositories.debate_repository import DebateConcurrencyError, DebateRepositoryError
from app.services.supabase_store import RepositoryError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Keep transport error policy separate from endpoint business logic."""
    app.add_exception_handler(RepositoryError, repository_error_handler)
    app.add_exception_handler(DebateConcurrencyError, debate_concurrency_error_handler)
    app.add_exception_handler(DebateRepositoryError, debate_repository_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


def repository_error_handler(request: Request, exc: RepositoryError) -> JSONResponse:
    logger.warning("Repository request failed (error_type=%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Persistence service unavailable"})


def debate_concurrency_error_handler(request: Request, exc: DebateConcurrencyError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "Debate state changed; refresh the session and try again"},
    )


def debate_repository_error_handler(request: Request, exc: DebateRepositoryError) -> JSONResponse:
    logger.warning("Debate persistence request failed (error_type=%s)", type(exc).__name__)
    return JSONResponse(
        status_code=503, content={"detail": "Debate persistence service unavailable"}
    )


def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Provider exception messages may contain prompts or credentials. Log only
    # routing context and the exception type, while preserving JSON for clients.
    logger.error(
        "Unhandled request failure (method=%s, path=%s, error_type=%s)",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
