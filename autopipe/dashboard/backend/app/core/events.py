"""Application event handlers."""

from fastapi import FastAPI
from app.db.session import init_db, close_db
from app.core.security import setup_rate_limiter, close_rate_limiter


def create_start_app_handler(app: FastAPI):
    """Create startup handler."""
    async def start_app():
        """Start up event handler."""
        await init_db()
        await setup_rate_limiter()
    return start_app


def create_stop_app_handler(app: FastAPI):
    """Create shutdown handler."""
    async def stop_app():
        """Shutdown event handler."""
        await close_rate_limiter()
        await close_db()
    return stop_app
