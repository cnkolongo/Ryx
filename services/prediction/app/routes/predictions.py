"""Routes prédictions."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ryx_shared.models import PredictionWindow

router = APIRouter()


@router.get("/predictions/{patient_id}")
async def get_predictions(
    patient_id: UUID,
    window: PredictionWindow | None = Query(default=None),
):
    """Dernières prédictions pour un patient (par fenêtre optionnelle)."""
    # TODO: récupérer depuis DB
    return {"patient_id": str(patient_id), "window": window, "predictions": []}


@router.post("/predictions/{patient_id}/compute", status_code=202)
async def compute_predictions(patient_id: UUID):
    """Déclencher le calcul des prédictions."""
    import uuid
    return {"patient_id": str(patient_id), "job_id": str(uuid.uuid4()), "status": "queued"}
