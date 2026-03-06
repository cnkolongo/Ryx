"""Routes patients — Mini-DMI CRUD."""

from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ryx_shared.models import Patient, Demographics, Identifier, ExternalId

from ..database import get_db
from ..models.patient import PatientRow

logger = structlog.get_logger(__name__)
router = APIRouter()


class CreatePatientRequest(BaseModel):
    demographics: Demographics | None = None
    identifiers: list[Identifier] = []
    external_ids: list[ExternalId] = []
    quality_flags: list[str] = []


class PatientListResponse(BaseModel):
    data: list[Patient]
    pagination: dict


def _row_to_patient(row: PatientRow) -> Patient:
    return Patient(
        patient_id=UUID(row.patient_id),
        demographics=Demographics(**row.demographics) if row.demographics else None,
        identifiers=[Identifier(**i) for i in (row.identifiers or [])],
        external_ids=[ExternalId(**e) for e in (row.external_ids or [])],
        quality_flags=row.quality_flags or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/patients", response_model=Patient, status_code=201)
async def create_patient(
    body: CreatePatientRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: Annotated[str | None, Header()] = None,
):
    """Créer un nouveau patient dans le Mini-DMI."""
    patient_id = str(uuid4())
    row = PatientRow(
        patient_id=patient_id,
        demographics=body.demographics.model_dump() if body.demographics else None,
        identifiers=[i.model_dump() for i in body.identifiers],
        external_ids=[e.model_dump() for e in body.external_ids],
        quality_flags=body.quality_flags,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info("patient.created", patient_id=patient_id, user=x_user_id)
    return _row_to_patient(row)


@router.get("/patients", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Liste paginée des patients avec recherche basique."""
    offset = (page - 1) * per_page

    stmt = select(PatientRow)
    count_stmt = select(func.count()).select_from(PatientRow)

    if q:
        like = f"%{q}%"
        json_filter = or_(
            PatientRow.demographics["last_name"].astext.ilike(like),
            PatientRow.demographics["first_name"].astext.ilike(like),
        )
        stmt = stmt.where(json_filter)
        count_stmt = count_stmt.where(json_filter)

    total = (await db.scalar(count_stmt)) or 0
    rows = (await db.scalars(
        stmt.offset(offset).limit(per_page).order_by(PatientRow.created_at.desc())
    )).all()

    return PatientListResponse(
        data=[_row_to_patient(r) for r in rows],
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    )


@router.get("/patients/{patient_id}", response_model=Patient)
async def get_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Récupérer un patient par ID."""
    row = await db.get(PatientRow, str(patient_id))
    if not row:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    return _row_to_patient(row)


@router.get("/patients/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Timeline complète du patient (encounters + labs)."""
    from ..models.encounter import EncounterRow
    from ..models.lab_result import LabResultRow

    patient = await db.get(PatientRow, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")

    encounters = (await db.scalars(
        select(EncounterRow)
        .where(EncounterRow.patient_id == str(patient_id))
        .order_by(EncounterRow.start_at.desc())
    )).all()

    labs = (await db.scalars(
        select(LabResultRow)
        .where(LabResultRow.patient_id == str(patient_id))
        .order_by(LabResultRow.date.desc())
        .limit(50)
    )).all()

    return {
        "patient_id": str(patient_id),
        "encounters": [
            {
                "encounter_id": e.encounter_id,
                "type": e.encounter_type,
                "status": e.status,
                "start_at": e.start_at.isoformat(),
                "end_at": e.end_at.isoformat() if e.end_at else None,
                "service": e.service,
                "reason": e.reason,
            }
            for e in encounters
        ],
        "lab_trends": [
            {
                "lab_id": l.lab_id,
                "test": l.test,
                "value": float(l.value_numeric) if l.value_numeric is not None else l.value_text,
                "unit": l.unit,
                "date": l.date.isoformat(),
                "status": l.status,
            }
            for l in labs
        ],
        "findings": [],
        "documents": [],
    }


@router.post("/patients/search")
async def search_patients(body: dict, db: AsyncSession = Depends(get_db)):
    """Recherche full-text patients."""
    query = body.get("query", "")
    if not query:
        return {"data": [], "pagination": {"page": 1, "per_page": 20, "total": 0}}

    like = f"%{query}%"
    rows = (await db.scalars(
        select(PatientRow)
        .where(
            or_(
                PatientRow.demographics["last_name"].astext.ilike(like),
                PatientRow.demographics["first_name"].astext.ilike(like),
            )
        )
        .limit(20)
    )).all()

    return {
        "data": [_row_to_patient(r).model_dump(mode="json") for r in rows],
        "pagination": {"page": 1, "per_page": 20, "total": len(rows)},
    }
