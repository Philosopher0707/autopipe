"""AutoPipe Dashboard - FastAPI backend server.

A production-grade dashboard for monitoring ML pipelines with real-time
updates, model registry management, drift detection, and experiment tracking.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.events import create_start_app_handler, create_stop_app_handler
from app.core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await create_start_app_handler(app)()
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
        # Request body size limit - prevents memory exhaustion attacks
        # 10MB for regular API calls, file uploads handled separately
        max_request_body=10 * 1024 * 1024,
    )

    # Security headers middleware (must be first)
    app.add_middleware(SecurityHeadersMiddleware)

    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure via env vars for production
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
        max_age=600,
    )

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
