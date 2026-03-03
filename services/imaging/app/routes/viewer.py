"""Routes viewer — Proxy Orthanc + highlights."""

from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from ryx_shared.config import RyxConfig

router = APIRouter()
config = RyxConfig()


@router.get("/viewer/doc/{doc_id}")
async def view_document(doc_id: UUID):
    """PDF viewer avec highlights EvidenceRef."""
    # TODO: générer URL signée MinIO + overlay EvidenceRefs
    return {"doc_id": str(doc_id), "viewer_url": f"/viewer/doc/{doc_id}/render", "evidence_refs": []}


@router.get("/viewer/dicom/{study_id}")
async def view_dicom(study_id: UUID):
    """DICOM viewer (OHIF) via Orthanc."""
    orthanc_url = f"{config.orthanc_url}/app/explorer.html#study?uuid=TODO"
    return {"study_id": str(study_id), "viewer_url": orthanc_url}


@router.get("/viewer/dicom/{study_id}/thumbnail")
async def get_thumbnail(study_id: UUID):
    """Thumbnail d'une étude DICOM."""
    # TODO: proxy vers Orthanc /instances/{id}/preview
    raise HTTPException(status_code=404, detail="Thumbnail non disponible")
