"""Routes admin — Jobs, health détaillé, Knowledge Pack."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/admin/health")
async def detailed_health():
    """Health check détaillé de tous les services."""
    # TODO: ping chaque service
    return {
        "status": "degraded",
        "services": {},
        "note": "Health checks détaillés à implémenter",
    }


@router.get("/admin/jobs")
async def list_jobs(status: str | None = None, page: int = 1, per_page: int = 20):
    """File de jobs avec filtres."""
    return {"data": [], "pagination": {"page": page, "per_page": per_page, "total": 0}}


@router.post("/admin/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry manuel d'un job."""
    return {"job_id": job_id, "status": "queued"}


@router.get("/admin/knowledge-pack/version")
async def knowledge_pack_version():
    """Version du Knowledge Pack installé."""
    from ryx_shared.config import RyxConfig
    config = RyxConfig()
    return {"version": config.knowledge_pack_version, "path": config.knowledge_pack_path}
