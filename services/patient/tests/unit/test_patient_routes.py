"""Tests unitaires patient service — CRUD patients et encounters.

Utilise SQLite en mémoire (pas besoin de PostgreSQL).
"""

import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

sys.path.insert(0, str(Path(__file__).parents[4] / "packages" / "shared"))

# ─── Setup DB SQLite en mémoire ───────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestBase(DeclarativeBase):
    pass


# Importer les modèles en utilisant TestBase
from app.models.patient import PatientRow
from app.models.encounter import EncounterRow
from app.models.lab_result import LabResultRow

# Rebinder les models sur TestBase pour les tests
PatientRow.__table__.metadata = TestBase.metadata if hasattr(TestBase, 'metadata') else PatientRow.__table__.metadata


@pytest_asyncio.fixture
async def test_engine():
    from app.database import Base
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    """Client HTTP avec DB en mémoire."""
    from app.main import app
    from app.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Tests patients ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreatePatient:
    async def test_create_patient_minimal(self, client):
        """Créer un patient sans données → 201."""
        resp = await client.post("/v1/patients", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert "patient_id" in data
        assert data["demographics"] is None

    async def test_create_patient_with_demographics(self, client):
        resp = await client.post("/v1/patients", json={
            "demographics": {
                "first_name": "Jean",
                "last_name": "Kabila",
                "sex": "M",
                "date_of_birth": "1980-05-15",
            }
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["demographics"]["last_name"] == "Kabila"
        assert data["demographics"]["first_name"] == "Jean"

    async def test_create_patient_with_identifiers(self, client):
        resp = await client.post("/v1/patients", json={
            "identifiers": [{"type": "national_id", "value": "CG-12345"}],
            "quality_flags": ["no_dob"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["identifiers"]) == 1
        assert data["identifiers"][0]["value"] == "CG-12345"
        assert "no_dob" in data["quality_flags"]


@pytest.mark.asyncio
class TestGetPatient:
    async def test_get_existing_patient(self, client):
        create = await client.post("/v1/patients", json={
            "demographics": {"last_name": "Mbeki", "first_name": "Amara"}
        })
        patient_id = create.json()["patient_id"]

        resp = await client.get(f"/v1/patients/{patient_id}")
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == patient_id

    async def test_get_nonexistent_patient_404(self, client):
        resp = await client.get(f"/v1/patients/{uuid4()}")
        assert resp.status_code == 404

    async def test_get_invalid_uuid_422(self, client):
        resp = await client.get("/v1/patients/not-a-uuid")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestListPatients:
    async def test_list_empty(self, client):
        resp = await client.get("/v1/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    async def test_list_with_patients(self, client):
        for name in ["Alice", "Bob", "Charlie"]:
            await client.post("/v1/patients", json={
                "demographics": {"last_name": name}
            })
        resp = await client.get("/v1/patients")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 3

    async def test_list_pagination(self, client):
        for i in range(5):
            await client.post("/v1/patients", json={
                "demographics": {"last_name": f"Patient{i}"}
            })
        resp = await client.get("/v1/patients?page=1&per_page=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3

    async def test_list_search_by_name(self, client):
        await client.post("/v1/patients", json={"demographics": {"last_name": "Dupont"}})
        await client.post("/v1/patients", json={"demographics": {"last_name": "Durand"}})
        await client.post("/v1/patients", json={"demographics": {"last_name": "Martin"}})

        resp = await client.get("/v1/patients?q=Du")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 2


@pytest.mark.asyncio
class TestPatientTimeline:
    async def test_timeline_empty_patient(self, client):
        create = await client.post("/v1/patients", json={})
        patient_id = create.json()["patient_id"]

        resp = await client.get(f"/v1/patients/{patient_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == patient_id
        assert data["encounters"] == []
        assert data["lab_trends"] == []

    async def test_timeline_with_encounters(self, client):
        create = await client.post("/v1/patients", json={})
        patient_id = create.json()["patient_id"]

        await client.post("/v1/encounters", json={
            "patient_id": patient_id,
            "start_at": "2024-01-15T08:00:00",
            "encounter_type": "outpatient",
            "reason": "Consultation paludisme",
        })

        resp = await client.get(f"/v1/patients/{patient_id}/timeline")
        assert resp.status_code == 200
        assert len(resp.json()["encounters"]) == 1

    async def test_timeline_nonexistent_patient_404(self, client):
        resp = await client.get(f"/v1/patients/{uuid4()}/timeline")
        assert resp.status_code == 404


# ─── Tests encounters ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateEncounter:
    async def test_create_encounter(self, client):
        patient = await client.post("/v1/patients", json={})
        patient_id = patient.json()["patient_id"]

        resp = await client.post("/v1/encounters", json={
            "patient_id": patient_id,
            "start_at": "2024-03-01T09:00:00",
            "encounter_type": "emergency",
            "reason": "Fièvre aiguë",
            "service": "Urgences",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == patient_id
        assert data["encounter_type"] == "emergency"
        assert data["reason"] == "Fièvre aiguë"

    async def test_create_encounter_default_type(self, client):
        patient = await client.post("/v1/patients", json={})
        patient_id = patient.json()["patient_id"]

        resp = await client.post("/v1/encounters", json={
            "patient_id": patient_id,
            "start_at": "2024-03-01T09:00:00",
        })
        assert resp.status_code == 201
        assert resp.json()["encounter_type"] == "outpatient"


@pytest.mark.asyncio
class TestGetEncounter:
    async def test_get_encounter(self, client):
        patient = await client.post("/v1/patients", json={})
        patient_id = patient.json()["patient_id"]
        enc = await client.post("/v1/encounters", json={
            "patient_id": patient_id,
            "start_at": "2024-03-01T09:00:00",
        })
        encounter_id = enc.json()["encounter_id"]

        resp = await client.get(f"/v1/encounters/{encounter_id}")
        assert resp.status_code == 200
        assert resp.json()["encounter_id"] == encounter_id

    async def test_get_nonexistent_encounter_404(self, client):
        resp = await client.get(f"/v1/encounters/{uuid4()}")
        assert resp.status_code == 404

    async def test_get_encounter_labs_empty(self, client):
        patient = await client.post("/v1/patients", json={})
        patient_id = patient.json()["patient_id"]
        enc = await client.post("/v1/encounters", json={
            "patient_id": patient_id,
            "start_at": "2024-03-01T09:00:00",
        })
        encounter_id = enc.json()["encounter_id"]

        resp = await client.get(f"/v1/encounters/{encounter_id}/labs")
        assert resp.status_code == 200
        assert resp.json()["labs"] == []
