"""API v1 root router."""

from fastapi import APIRouter

from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(discovery_router, prefix="/discovery", tags=["Discovery"])
api_v1_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
