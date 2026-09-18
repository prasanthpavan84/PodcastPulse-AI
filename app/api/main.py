"""FastAPI application entry point."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import ctx_request_id, get_logger, setup_logging

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler."""
    setup_logging()
    logger.info("application_startup", app_name="PodcastPulse AI", version=settings.app_version)
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="PodcastPulse AI API",
    description="Backend API for PodcastPulse AI editorial video production platform.",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware with explicit configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assign or propagate X-Request-ID and attach to logging context."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = ctx_request_id.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        ctx_request_id.reset(token)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Standardized JSON response for domain and application errors."""
    logger.warn(
        "app_error_occurred",
        error_code=exc.code.value,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_dict()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled exceptions."""
    logger.exception("unhandled_server_exception", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
            }
        },
    )


# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")
