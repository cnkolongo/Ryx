"""Routes evidence — Preuves cliquables + statuts claims."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.claim import ClaimRow

router = APIRouter()


@router.get("/evidence/claims/{claim_id}")
async def get_claim(claim_id: UUID, db: AsyncSession = Depends(get_db)):
    """Détail d'un claim avec ses preuves."""
    row = await db.get(ClaimRow, str(claim_id))
    if not row:
        raise HTTPException(status_code=404, detail="Claim non trouvé")
    return {
        "claim_id": row.claim_id,
        "type": row.type,
        "text": row.text,
        "criticality": row.criticality,
        "status": row.status,
        "blocked_reason": row.blocked_reason,
        "evidence_refs": row.evidence_refs,
        "encounter_id": row.encounter_id,
        "patient_id": row.patient_id,
        "validated_by": row.validated_by,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/evidence/claims/{claim_id}/refs")
async def get_claim_evidence_refs(claim_id: UUID, db: AsyncSession = Depends(get_db)):
    """Preuves cliquables d'un claim (PDF bbox, DICOM slice, lab, knowledge)."""
    row = await db.get(ClaimRow, str(claim_id))
    if not row:
        raise HTTPException(status_code=404, detail="Claim non trouvé")
    return {"claim_id": str(claim_id), "evidence_refs": row.evidence_refs}


@router.get("/evidence/encounter/{encounter_id}/claims")
async def get_encounter_claims(
    encounter_id: UUID,
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Tous les claims d'un encounter, filtrables par statut."""
    stmt = select(ClaimRow).where(ClaimRow.encounter_id == str(encounter_id))
    if status:
        stmt = stmt.where(ClaimRow.status == status)
    stmt = stmt.order_by(ClaimRow.created_at.desc())

    rows = (await db.scalars(stmt)).all()
    return {
        "encounter_id": str(encounter_id),
        "claims": [
            {
                "claim_id": r.claim_id,
                "type": r.type,
                "text": r.text,
                "criticality": r.criticality,
                "status": r.status,
                "evidence_refs_count": len(r.evidence_refs or []),
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/evidence/blocked")
async def get_blocked_claims(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Claims bloqués par EvidenceGuard (nécessitent révision)."""
    rows = (await db.scalars(
        select(ClaimRow)
        .where(ClaimRow.status == "blocked")
        .order_by(ClaimRow.created_at.desc())
        .limit(limit)
    )).all()

    total = (await db.scalar(
        select(func.count()).select_from(ClaimRow).where(ClaimRow.status == "blocked")
    )) or 0

    return {
        "data": [
            {
                "claim_id": r.claim_id,
                "type": r.type,
                "text": r.text,
                "criticality": r.criticality,
                "blocked_reason": r.blocked_reason,
                "patient_id": r.patient_id,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
    }
