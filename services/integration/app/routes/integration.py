"""Routes integration — Connectors DMI."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/integration/connectors")
async def list_connectors():
    """Liste des connecteurs disponibles."""
    return {"connectors": [
        {"id": "fhir-r4", "name": "HL7 FHIR R4", "status": "available"},
        {"id": "openmrs", "name": "OpenMRS", "status": "available"},
        {"id": "csv-import", "name": "CSV Import", "status": "available"},
    ]}


@router.post("/integration/connectors/{connector_id}/sync", status_code=202)
async def trigger_sync(connector_id: str):
    """Déclencher une sync."""
    import uuid
    return {"connector_id": connector_id, "job_id": str(uuid.uuid4()), "status": "queued"}


@router.get("/integration/connectors/{connector_id}/status")
async def get_connector_status(connector_id: str):
    """Statut du connecteur."""
    return {"connector_id": connector_id, "status": "unknown", "last_sync": None}


@router.post("/integration/connectors/{connector_id}/test")
async def test_connector(connector_id: str):
    """Tester la connexion."""
    # TODO: implémenter
    return {"connector_id": connector_id, "reachable": False}
