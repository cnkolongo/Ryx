"""Routes encounters — Mini-DMI encounters."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Annotated

from ryx_shared.models import Encounter, EncounterType

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


@router.post("/encounters", response_model=Encounter, status_code=201)
async def create_encounter(
    body: CreateEncounterRequest,
    x_user_id: Annotated[str | None, Header()] = None,
):
    """Créer un encounter (consultation, hospitalisation, urgence)."""
    from datetime import datetime
    from uuid import uuid4
    encounter = Encounter(
        patient_id=body.patient_id,
        start_at=datetime.fromisoformat(body.start_at),
        end_at=datetime.fromisoformat(body.end_at) if body.end_at else None,
        service=body.service,
        reason=body.reason,
        location=body.location,
        encounter_type=body.encounter_type,
        created_by=UUID(x_user_id) if x_user_id else uuid4(),
    )
    # TODO: persister en DB
    logger.info("encounter.created", encounter_id=str(encounter.encounter_id))
    return encounter


@router.get("/encounters/{encounter_id}", response_model=Encounter)
async def get_encounter(encounter_id: UUID):
    """Récupérer un encounter par ID."""
    raise HTTPException(status_code=404, detail="Encounter non trouvé")


@router.get("/encounters/{encounter_id}/documents")
async def get_encounter_documents(encounter_id: UUID):
    """Documents liés à cet encounter."""
    return {"encounter_id": str(encounter_id), "documents": []}


@router.get("/encounters/{encounter_id}/labs")
async def get_encounter_labs(encounter_id: UUID):
    """Labs liés à cet encounter."""
    return {"encounter_id": str(encounter_id), "labs": []}
