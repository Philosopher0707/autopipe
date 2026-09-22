"""AutoPipe Dashboard - FastAPI backend server.

A production-grade dashboard for monitoring ML pipelines with real-time
updates, model registry management, drift detection, and experiment tracking.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.core.body_limit import RequestSizeLimitMiddleware
from app.core.config import settings
from app.core.events import create_start_app_handler, create_stop_app_handler
from app.core.rate_limit_headers import RateLimitHeadersMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def enforce_secret_key_policy() -> None:
    """Refuse an ephemeral JWT secret outside development (invariant I18).

    ``SECRET_KEY`` falls back to a value generated at import time. That value is
    per-process, so every restart and every additional worker silently
    invalidates all issued tokens. Previously nothing said so: the service
    looked healthy while logging everyone out. Development is still allowed to
    run this way, loudly; anything else must configure a key.
    """
    if not settings.SECRET_KEY_IS_EPHEMERAL:
        return

    if settings.ENVIRONMENT.strip().lower() in {"development", "test", "local"}:
        logger.warning(
            "SECRET_KEY is not set: a per-process key was generated. Issued tokens "
            "will not survive a restart and will not validate across workers. Set "
            "SECRET_KEY before deploying (ENVIRONMENT=%s).",
            settings.ENVIRONMENT,
        )
        return

    raise RuntimeError(
        f"SECRET_KEY must be set when ENVIRONMENT={settings.ENVIRONMENT!r}: the "
        "generated per-process key would invalidate every token on each restart "
        "and across workers. Refusing to start."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    enforce_secret_key_policy()
    await create_start_app_handler(app)()

    # Runs left RUNNING by a previous process can never finish on their own.
    from app.executor.runner import set_event_loop, sweep_orphaned_runs

    sweep_orphaned_runs()
    app.state.event_loop = asyncio.get_running_loop()
    set_event_loop(app.state.event_loop)
    yield
    # Shutdown
    await create_stop_app_handler(app)()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
        # NOTE: there is deliberately no `max_request_body` argument here.
        # FastAPI has no such parameter, so passing it silently stored the value
        # in `FastAPI.extra` and enforced nothing while the comment claimed it
        # prevented memory exhaustion. The real limit is the
        # RequestSizeLimitMiddleware added below (invariant I18).
    )

    # Middleware order matters: `add_middleware` makes each newly added
    # middleware the OUTERMOST one, so these calls read innermost-to-outermost.
    # Security headers are added last on purpose — they must also appear on
    # responses produced by the other middleware (host rejection, 413s). The
    # previous order made them innermost, so those responses carried no headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
        ],
        max_age=600,
    )

    # Host header validation. The previous default was ["*"], which accepted any
    # Host and made this middleware a no-op; ALLOWED_HOSTS now defaults to the
    # hosts a local-first deployment is actually reached on.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # Real request-body limit, in place of the constructor argument above.
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.MAX_REQUEST_BODY_SIZE,
    )

    # Security headers on every response produced by the middleware below it
    # (host rejection, 413s, CORS). Not the outermost — RateLimitHeaders is.
    app.add_middleware(SecurityHeadersMiddleware)

    # Stamps X-RateLimit-* from request.state (set by check_default_rate_limit).
    # Added after SecurityHeadersMiddleware so it is outer and its headers survive
    # on responses the inner middlewares (413, 429, CORS) produce.
    app.add_middleware(RateLimitHeadersMiddleware)

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Mount static files for frontend (if built)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    except RuntimeError:
        logger.warning(
            "Static files directory 'static' not found; skipping. "
            "Build the frontend to enable static file serving."
        )

    return app


app = create_application()


@app.get("/")
async def root():
    """Root endpoint - redirect to docs."""
    return {
        "message": "AutoPipe Dashboard API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "autopipe-dashboard"}
