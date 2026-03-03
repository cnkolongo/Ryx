"""Routes imaging — Études DICOM."""

from uuid import UUID
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()


@router.post("/imaging/import", status_code=201)
async def import_dicom(file: UploadFile = File(...), encounter_id: str = None, patient_id: str = None):
    """Import d'une étude DICOM."""
    import uuid
    return {"study_id": str(uuid.uuid4()), "status": "queued", "message": "Import DICOM en cours"}


@router.get("/imaging/studies/{study_id}")
async def get_study(study_id: UUID):
    """Metadata d'une étude DICOM."""
    raise HTTPException(status_code=404, detail="Étude non trouvée")


@router.post("/imaging/studies/{study_id}/analyze", status_code=202)
async def trigger_pillar0(study_id: UUID):
    """Déclencher l'analyse Pillar-0."""
    import uuid
    return {"study_id": str(study_id), "job_id": str(uuid.uuid4()), "status": "queued"}


@router.get("/imaging/studies/{study_id}/findings")
async def get_findings(study_id: UUID):
    """Findings Pillar-0 pour une étude."""
    return {"study_id": str(study_id), "findings": []}
