"""RYX Shared — Types, models, events et utilitaires communs."""

from .models import (
    Patient,
    Demographics,
    Identifier,
    ExternalId,
    Encounter,
    Document,
    OcrBlock,
    BoundingBox,
    LabResult,
    ReferenceRange,
    ImagingStudy,
    ImagingSeries,
    Finding,
    Report,
    ReportSections,
    Prediction,
    PredictionFactor,
    KnowledgeDoc,
    KnowledgeChunk,
)
from .evidence import (
    EvidenceRef,
    DocEvidenceRef,
    DicomEvidenceRef,
    LabEvidenceRef,
    KnowledgeEvidenceRef,
)
from .claims import (
    Claim,
    ClaimType,
    ClaimStatus,
    CriticalityLevel,
)
from .events import (
    RyxEvent,
    EventBus,
    TOPICS,
)
from .jobs import (
    Job,
    JobType,
    JobStatus,
    JobLocation,
)
from .config import RyxConfig, RyxMode

__all__ = [
    # Models
    "Patient", "Demographics", "Identifier", "ExternalId",
    "Encounter", "Document", "OcrBlock", "BoundingBox",
    "LabResult", "ReferenceRange",
    "ImagingStudy", "ImagingSeries",
    "Finding", "Report", "ReportSections",
    "Prediction", "PredictionFactor",
    "KnowledgeDoc", "KnowledgeChunk",
    # Evidence
    "EvidenceRef", "DocEvidenceRef", "DicomEvidenceRef",
    "LabEvidenceRef", "KnowledgeEvidenceRef",
    # Claims
    "Claim", "ClaimType", "ClaimStatus", "CriticalityLevel",
    # Events
    "RyxEvent", "EventBus", "TOPICS",
    # Jobs
    "Job", "JobType", "JobStatus", "JobLocation",
    # Config
    "RyxConfig", "RyxMode",
]
