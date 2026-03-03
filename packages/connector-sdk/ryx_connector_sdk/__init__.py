"""RYX Connector SDK — SDK standard pour connecteurs DMI."""

from .interfaces import (
    ConnectorMode,
    ConnectorConfig,
    SyncResult,
    PatientRecord,
    EncounterRecord,
    DocumentRecord,
    BaseConnector,
)
from .registry import ConnectorRegistry

__all__ = [
    "ConnectorMode",
    "ConnectorConfig",
    "SyncResult",
    "PatientRecord",
    "EncounterRecord",
    "DocumentRecord",
    "BaseConnector",
    "ConnectorRegistry",
]
