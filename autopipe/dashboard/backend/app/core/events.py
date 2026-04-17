"""Application event handlers."""

from fastapi import FastAPI
from app.db.session import init_db, close_db


def create_start_app_handler(app: FastAPI):
    """Create startup handler."""
    async def start_app():
        """Start up event handler."""
        await init_db()
    return start_app


def create_stop_app_handler(app: FastAPI):
    """Create shutdown handler."""
    async def stop_app():
        """Shutdown event handler."""
        await close_db()
    return stop_app
