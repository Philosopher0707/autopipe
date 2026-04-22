"""Main API router."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, automl, charts, dashboard, drift, explainability, experiments, models, pipelines, runs, websocket

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(automl.router, prefix="/trials", tags=["automl"])
api_router.include_router(charts.router, prefix="/charts", tags=["charts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(experiments.router, prefix="/experiments", tags=["experiments"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(drift.router, prefix="/drift", tags=["drift"])
api_router.include_router(explainability.router, prefix="/explainability", tags=["explainability"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
