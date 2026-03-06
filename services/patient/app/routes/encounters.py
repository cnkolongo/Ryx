"""Routes encounters — Mini-DMI encounters."""

from uuid import UUID, uuid4
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from ryx_shared.models import Encounter, EncounterType

from ..database import get_db
from ..models.encounter import EncounterRow
from ..models.lab_result import LabResultRow

logger = structlog.get_logger(__name__)
router = APIRouter()


class CreateEncounterRequest(BaseModel):
    patient_id: UUID
    start_at: str
    end_at: str | None = None
    service: str | None = None
    reason: str | None = None
    location: str | None = None
    encounter_type: EncounterType = EncounterType.OUTPATIENT


def _row_to_encounter(row: EncounterRow) -> Encounter:
    return Encounter(
        encounter_id=UUID(row.encounter_id),
        patient_id=UUID(row.patient_id),
        encounter_type=EncounterType(row.encounter_type),
        start_at=row.start_at,
        end_at=row.end_at,
        service=row.service,
        reason=row.reason,
        location=row.location,
        created_by=UUID(row.created_by) if row.created_by else None,
        created_at=row.created_at,
    )


@router.post("/encounters", response_model=Encounter, status_code=201)
async def create_encounter(
    body: CreateEncounterRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: Annotated[str | None, Header()] = None,
):
    """Créer un encounter (consultation, hospitalisation, urgence)."""
    row = EncounterRow(
        encounter_id=str(uuid4()),
        patient_id=str(body.patient_id),
        encounter_type=body.encounter_type.value,
        start_at=datetime.fromisoformat(body.start_at),
        end_at=datetime.fromisoformat(body.end_at) if body.end_at else None,
        service=body.service,
        reason=body.reason,
        location=body.location,
        created_by=x_user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info("encounter.created", encounter_id=row.encounter_id)
    return _row_to_encounter(row)


@router.get("/encounters/{encounter_id}", response_model=Encounter)
async def get_encounter(
    encounter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Récupérer un encounter par ID."""
    row = await db.get(EncounterRow, str(encounter_id))
    if not row:
        raise HTTPException(status_code=404, detail="Encounter non trouvé")
    return _row_to_encounter(row)


@router.get("/encounters/{encounter_id}/documents")
async def get_encounter_documents(encounter_id: UUID):
    """Documents liés à cet encounter (rempli par ingestion service)."""
    return {"encounter_id": str(encounter_id), "documents": []}


@router.get("/encounters/{encounter_id}/labs")
async def get_encounter_labs(
    encounter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Labs liés à cet encounter."""
    labs = (await db.scalars(
        select(LabResultRow)
        .where(LabResultRow.encounter_id == str(encounter_id))
        .order_by(LabResultRow.date.desc())
    )).all()

    return {
        "encounter_id": str(encounter_id),
        "labs": [
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
    }
