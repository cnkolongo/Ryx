"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "gateway"}


@router.get("/health/ready", tags=["health"])
async def readiness():
    # TODO: vérifier DB + Redis
    return {"status": "ready", "service": "gateway"}
