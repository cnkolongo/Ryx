"""Routes rapports — Génération et consultation."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException

from ryx_shared.models import Report

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/reports/{encounter_id}/latest", response_model=Report)
async def get_latest_report(encounter_id: UUID):
    """Dernier rapport IA d'un encounter."""
    # TODO: récupérer depuis DB
    raise HTTPException(status_code=404, detail="Aucun rapport disponible")


@router.post("/reports/{encounter_id}/generate", status_code=202)
async def generate_report(encounter_id: UUID):
    """Déclencher la génération d'un rapport (async)."""
    import uuid
    job_id = str(uuid.uuid4())
    # TODO: publier medgemma.requested
    return {
        "message": "Génération du rapport en cours",
        "job_id": job_id,
        "encounter_id": str(encounter_id),
    }


@router.get("/reports/{report_id}/claims")
async def get_report_claims(report_id: UUID):
    """Claims d'un rapport avec statuts EvidenceGuard."""
    # TODO: récupérer depuis DB
    return {"report_id": str(report_id), "claims": []}


@router.patch("/reports/{report_id}/claims/{claim_id}")
async def update_claim(report_id: UUID, claim_id: UUID, body: dict):
    """Valider/rejeter un claim (action clinicien)."""
    # TODO: implémenter avec audit log
    return {"claim_id": str(claim_id), "status": body.get("status")}
