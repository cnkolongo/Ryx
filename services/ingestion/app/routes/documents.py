"""Routes ingestion de documents."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Header, Request, UploadFile

from ryx_shared.models import DocumentType
from ryx_shared.config import RyxConfig
from ..storage import upload_document

logger = structlog.get_logger(__name__)
config = RyxConfig()
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "application/dicom",
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/documents/upload", status_code=201)
async def upload_document_endpoint(
    request: Request,
    file: UploadFile = File(...),
    encounter_id: str = Form(...),
    patient_id: str = Form(...),
    document_type: DocumentType = Form(default=DocumentType.OTHER),
    document_date: str | None = Form(default=None),
    x_user_id: Annotated[str | None, Header()] = None,
):
    """
    Upload d'un document (PDF, image, DICOM).
    Stockage dans MinIO + publication event ingestion.received.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Type de fichier non supporté : {file.content_type}. "
                   f"Acceptés : {ALLOWED_MIME_TYPES}",
        )

    file_data = await file.read()

    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"Fichier trop volumineux : {len(file_data)} bytes. Max : {MAX_FILE_SIZE}",
        )

    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    storage_path = await upload_document(
        file_data=file_data,
        patient_id=patient_id,
        doc_id=doc_id,
        filename=file.filename or f"document_{doc_id}",
        content_type=file.content_type,
    )

    logger.info(
        "ingestion.document_received",
        doc_id=doc_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        file_size=len(file_data),
        content_type=file.content_type,
    )

    # Publier event ingestion.received → déclenche PreprocessAgent
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus:
        await event_bus.publish(
            "ingestion.received",
            {
                "doc_id": doc_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "document_type": document_type.value,
                "storage_path": storage_path,
                "job_id": job_id,
                "original_filename": file.filename,
                "mime_type": file.content_type,
            },
            source="ingestion",
        )
    else:
        logger.warning("ingestion.event_bus_unavailable", doc_id=doc_id)

    return {
        "doc_id": doc_id,
        "status": "queued",
        "job_id": job_id,
        "storage_path": storage_path,
        "message": "Document reçu, preprocessing en cours",
    }


@router.get("/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Statut du preprocessing d'un document."""
    # TODO: récupérer depuis DB (table ingestion_jobs) — nécessite P0.1 étendu
    return {"doc_id": doc_id, "status": "queued", "job_id": None}
