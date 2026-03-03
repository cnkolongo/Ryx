"""Interfaces standard pour connecteurs DMI RYX."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import AsyncIterator
from uuid import UUID

from pydantic import BaseModel


class ConnectorMode(str, Enum):
    SHADOW = "shadow"      # lecture seule
    LINK = "link"          # mapping IDs uniquement
    WRITE_BACK = "write_back"  # push rapports/alertes vers DMI


class ConnectorConfig(BaseModel):
    connector_id: str
    name: str
    mode: ConnectorMode = ConnectorMode.SHADOW
    base_url: str | None = None
    api_key: str | None = None
    username: str | None = None
    password: str | None = None
    extra: dict = {}


class SyncResult(BaseModel):
    connector_id: str
    synced_at: datetime
    patients_synced: int = 0
    encounters_synced: int = 0
    documents_synced: int = 0
    errors: list[str] = []
    success: bool = True


class PatientRecord(BaseModel):
    """Patient normalisé depuis une source externe."""
    external_id: str
    system: str  # "openmrs" | "fhir" | "csv"
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None  # ISO date string
    sex: str | None = None
    phone: str | None = None
    raw: dict = {}  # données brutes source


class EncounterRecord(BaseModel):
    """Encounter normalisé depuis une source externe."""
    external_id: str
    patient_external_id: str
    system: str
    start_at: datetime
    end_at: datetime | None = None
    service: str | None = None
    raw: dict = {}


class DocumentRecord(BaseModel):
    """Document normalisé depuis une source externe."""
    external_id: str
    encounter_external_id: str | None = None
    patient_external_id: str | None = None
    system: str
    url: str | None = None  # URL pour téléchargement
    content_type: str | None = None
    document_date: datetime | None = None
    raw: dict = {}


class BaseConnector(ABC):
    """
    Interface de base pour tous les connecteurs DMI.

    Implémenter cette classe pour connecter un DMI externe à RYX.
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config

    @property
    def connector_id(self) -> str:
        return self.config.connector_id

    @property
    def mode(self) -> ConnectorMode:
        return self.config.mode

    # ─── Méthodes obligatoires ────────────────────────────────────────────────

    @abstractmethod
    async def test_connection(self) -> bool:
        """Tester la connectivité avec la source DMI."""
        ...

    @abstractmethod
    async def pull_patients(self, since: datetime | None = None) -> AsyncIterator[PatientRecord]:
        """Récupérer les patients (modifiés depuis `since`)."""
        ...

    @abstractmethod
    async def pull_encounters(
        self, since: datetime | None = None
    ) -> AsyncIterator[EncounterRecord]:
        """Récupérer les encounters."""
        ...

    # ─── Méthodes optionnelles ────────────────────────────────────────────────

    async def pull_documents(
        self, since: datetime | None = None
    ) -> AsyncIterator[DocumentRecord]:
        """Récupérer les documents. Override si supporté."""
        return
        yield  # Make it a generator

    async def pull_imaging_refs(
        self, since: datetime | None = None
    ) -> AsyncIterator[DocumentRecord]:
        """Récupérer les références DICOM."""
        return
        yield

    # ─── Write-back (optionnel, mode WRITE_BACK uniquement) ──────────────────

    async def push_report(self, encounter_id: str, report_ref: dict) -> bool:
        """Pousser un rapport RYX vers le DMI."""
        if self.mode != ConnectorMode.WRITE_BACK:
            raise NotImplementedError("Write-back requires mode=WRITE_BACK")
        raise NotImplementedError("push_report not implemented")

    async def push_alert(self, patient_id: str, alert_ref: dict) -> bool:
        """Pousser une alerte RYX vers le DMI."""
        if self.mode != ConnectorMode.WRITE_BACK:
            raise NotImplementedError("Write-back requires mode=WRITE_BACK")
        raise NotImplementedError("push_alert not implemented")

    # ─── Mapping IDs ──────────────────────────────────────────────────────────

    async def map_external_id(self, external_id: str) -> UUID | None:
        """Retourner le patient_id RYX correspondant à un ID externe."""
        return None
