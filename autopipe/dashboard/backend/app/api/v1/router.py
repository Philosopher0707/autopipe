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
from app.core.security import check_default_rate_limit
from fastapi import APIRouter, Depends

api_router = APIRouter()

# Every data route requires a valid JWT. /auth is the only public surface.
_auth = [Depends(get_current_user)]

# Default rate limit (100/min per client) on every HTTP route. Rate limit
# runs BEFORE auth so unauthenticated hammering also counts. Login/register
# keep their stricter per-endpoint limits on top; they share no bucket with
# this one (separate limiter identifiers), so there is no double-count to
# avoid — and excluding /auth would leave /auth/me unlimited.
_rl = [Depends(check_default_rate_limit)]

api_router.include_router(auth.router, prefix="/auth", tags=["auth"], dependencies=_rl)

# Include all endpoint routers
api_router.include_router(
    automl.router, prefix="/trials", tags=["automl"], dependencies=_rl + _auth
)
api_router.include_router(
    charts.router, prefix="/charts", tags=["charts"], dependencies=_rl + _auth
)
api_router.include_router(
    dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=_rl + _auth
)
api_router.include_router(
    pipelines.router, prefix="/pipelines", tags=["pipelines"], dependencies=_rl + _auth
)
api_router.include_router(runs.router, prefix="/runs", tags=["runs"], dependencies=_rl + _auth)
api_router.include_router(
    experiments.router, prefix="/experiments", tags=["experiments"], dependencies=_rl + _auth
)
api_router.include_router(
    models.router, prefix="/models", tags=["models"], dependencies=_rl + _auth
)
api_router.include_router(drift.router, prefix="/drift", tags=["drift"], dependencies=_rl + _auth)
api_router.include_router(
    explainability.router,
    prefix="/explainability",
    tags=["explainability"],
    dependencies=_rl + _auth,
)
api_router.include_router(
    features.router, prefix="/features", tags=["features"], dependencies=_rl + _auth
)
api_router.include_router(
    projects.router, prefix="/projects", tags=["projects"], dependencies=_rl + _auth
)
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
