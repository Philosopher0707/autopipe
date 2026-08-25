"""Main API router."""

from app.api.v1.endpoints import (
    auth,
    automl,
    charts,
    dashboard,
    drift,
    experiments,
    explainability,
    features,
    models,
    pipelines,
    projects,
    runs,
    websocket,
)
from app.core.auth import get_current_user
from fastapi import APIRouter, Depends

api_router = APIRouter()

# Every data route requires a valid JWT. /auth is the only public surface.
_auth = [Depends(get_current_user)]

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(automl.router, prefix="/trials", tags=["automl"], dependencies=_auth)
api_router.include_router(charts.router, prefix="/charts", tags=["charts"], dependencies=_auth)
api_router.include_router(
    dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=_auth
)
api_router.include_router(
    pipelines.router, prefix="/pipelines", tags=["pipelines"], dependencies=_auth
)
api_router.include_router(runs.router, prefix="/runs", tags=["runs"], dependencies=_auth)
api_router.include_router(
    experiments.router, prefix="/experiments", tags=["experiments"], dependencies=_auth
)
api_router.include_router(models.router, prefix="/models", tags=["models"], dependencies=_auth)
api_router.include_router(drift.router, prefix="/drift", tags=["drift"], dependencies=_auth)
api_router.include_router(
    explainability.router, prefix="/explainability", tags=["explainability"], dependencies=_auth
)
api_router.include_router(
    features.router, prefix="/features", tags=["features"], dependencies=_auth
)
api_router.include_router(
    projects.router, prefix="/projects", tags=["projects"], dependencies=_auth
)
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
