"""Routes evidence — Preuves cliquables + statuts claims."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/evidence/claims/{claim_id}")
async def get_claim(claim_id: UUID):
    """Détail d'un claim avec ses preuves."""
    raise HTTPException(status_code=404, detail="Claim non trouvé")


@router.get("/evidence/claims/{claim_id}/refs")
async def get_claim_evidence_refs(claim_id: UUID):
    """Preuves cliquables d'un claim (PDF bbox, DICOM slice, lab, knowledge)."""
    return {"claim_id": str(claim_id), "evidence_refs": []}


@router.get("/evidence/blocked")
async def get_blocked_claims(limit: int = 20):
    """Claims bloqués par EvidenceGuard (nécessitent révision)."""
    return {"data": [], "total": 0}
