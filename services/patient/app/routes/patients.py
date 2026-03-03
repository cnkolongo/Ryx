"""Routes patients — Mini-DMI CRUD."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel

from ryx_shared.models import Patient, Demographics, Identifier, ExternalId

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


@router.post("/patients", response_model=Patient, status_code=201)
async def create_patient(
    body: CreatePatientRequest,
    x_user_id: Annotated[str | None, Header()] = None,
):
    """Créer un nouveau patient dans le Mini-DMI."""
    patient = Patient(
        demographics=body.demographics,
        identifiers=body.identifiers,
        external_ids=body.external_ids,
        quality_flags=body.quality_flags,
    )
    # TODO: persister en DB
    logger.info("patient.created", patient_id=str(patient.patient_id), user=x_user_id)
    return patient


@router.get("/patients", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
):
    """Liste paginée des patients avec recherche optionnelle."""
    # TODO: implémenter avec DB + Meilisearch
    return PatientListResponse(
        data=[],
        pagination={"page": page, "per_page": per_page, "total": 0, "total_pages": 0},
    )


@router.get("/patients/{patient_id}", response_model=Patient)
async def get_patient(patient_id: UUID):
    """Récupérer un patient par ID."""
    # TODO: récupérer depuis DB
    raise HTTPException(status_code=404, detail="Patient non trouvé")


@router.get("/patients/{patient_id}/timeline")
async def get_patient_timeline(patient_id: UUID):
    """Timeline complète du patient (encounters + docs + labs + findings)."""
    # TODO: agréger depuis DB
    return {
        "patient_id": str(patient_id),
        "encounters": [],
        "lab_trends": [],
        "findings": [],
        "documents": [],
    }


@router.post("/patients/search")
async def search_patients(body: dict):
    """Recherche full-text patients (Meilisearch)."""
    # TODO: intégrer Meilisearch
    return {"data": [], "pagination": {"page": 1, "per_page": 20, "total": 0}}
