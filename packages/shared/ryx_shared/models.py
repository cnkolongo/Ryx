"""RYX Data Models — Entités principales du domaine clinique."""

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .evidence import BoundingBox, EvidenceRef


# ─── Enums ────────────────────────────────────────────────────────────────────

class EncounterType(str, Enum):
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"


class EncounterStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    IMAGING = "imaging"
    CLINICAL_NOTE = "clinical_note"
    PRESCRIPTION = "prescription"
    OTHER = "other"


class LabStatus(str, Enum):
    NORMAL = "normal"
    ABNORMAL = "abnormal"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FindingSource(str, Enum):
    PILLAR0 = "pillar0"
    OCR = "ocr"
    CLINICIAN = "clinician"


class ReportStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class PredictionWindow(str, Enum):
    D30 = "30d"
    M6 = "6m"
    Y1 = "1y"
    Y2 = "2y"


class RiskBand(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Patient ──────────────────────────────────────────────────────────────────

class Demographics(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    dob_approximate: bool = False
    sex: str | None = None  # M | F | Unknown
    phone: str | None = None
    address: str | None = None


class Identifier(BaseModel):
    type: str  # "national_id" | "patient_number" | "name_phonetic"
    value: str
    issuer: str | None = None


class ExternalId(BaseModel):
    system: str  # "openmrs" | "dhis2" | "fhir" | "csv_import"
    value: str
    linked_at: datetime = Field(default_factory=datetime.utcnow)


class Patient(BaseModel):
    patient_id: UUID = Field(default_factory=uuid4)
    demographics: Demographics | None = None
    identifiers: list[Identifier] = Field(default_factory=list)
    external_ids: list[ExternalId] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)  # "no_dob", "approximate_age"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Encounter ────────────────────────────────────────────────────────────────

class Encounter(BaseModel):
    encounter_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    start_at: datetime
    end_at: datetime | None = None
    service: str | None = None
    reason: str | None = None
    location: str | None = None
    encounter_type: EncounterType = EncounterType.OUTPATIENT
    status: EncounterStatus = EncounterStatus.ACTIVE
    created_by: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Document ─────────────────────────────────────────────────────────────────

class OcrBlock(BaseModel):
    block_id: str
    page: int = Field(ge=1)
    bbox: BoundingBox
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    block_type: str = "paragraph"  # paragraph | table | header | value


class Document(BaseModel):
    doc_id: UUID = Field(default_factory=uuid4)
    encounter_id: UUID
    patient_id: UUID
    type: DocumentType = DocumentType.OTHER
    original_filename: str | None = None
    mime_type: str
    storage_path: str
    pages: int | None = None
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rescan_needed: bool = False
    ocr_blocks: list[OcrBlock] = Field(default_factory=list)
    language: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    preprocessed_at: datetime | None = None


# ─── Lab Result ───────────────────────────────────────────────────────────────

class ReferenceRange(BaseModel):
    low: float | None = None
    high: float | None = None
    text: str | None = None


class LabResult(BaseModel):
    lab_id: UUID = Field(default_factory=uuid4)
    encounter_id: UUID
    patient_id: UUID
    document_id: UUID | None = None
    test: str
    value: float | str
    unit: str | None = None
    ref_range: ReferenceRange | None = None
    date: datetime
    status: LabStatus = LabStatus.UNKNOWN
    extracted_by: str = "ocr"  # ocr | clinician | connector


# ─── Imaging ──────────────────────────────────────────────────────────────────

class ImagingSeries(BaseModel):
    series_id: str
    orthanc_series_id: str
    description: str | None = None
    instances_count: int = 0


class ImagingStudy(BaseModel):
    study_id: UUID = Field(default_factory=uuid4)
    encounter_id: UUID
    patient_id: UUID
    orthanc_study_id: str
    modality: str  # CT | MRI | CXR | ECG
    body_part: str | None = None
    date: datetime
    series: list[ImagingSeries] = Field(default_factory=list)
    pillar0_status: str | None = None  # queued | running | done | failed


# ─── Finding ──────────────────────────────────────────────────────────────────

class Finding(BaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    encounter_id: UUID | None = None
    source: FindingSource
    label: str
    severity: str | None = None  # mild | moderate | severe | critical
    time: datetime
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    clinician_confirmed: bool | None = None
    clinician_note: str | None = None


# ─── Report ───────────────────────────────────────────────────────────────────

class ReportSections(BaseModel):
    summary: str | None = None
    timeline: str | None = None
    labs_trend: str | None = None
    imaging_findings: str | None = None
    active_problems: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)


class Report(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    encounter_id: UUID
    patient_id: UUID
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str
    sections: ReportSections = Field(default_factory=ReportSections)
    recommendations: list = Field(default_factory=list)  # list[Claim]
    questions: list[str] = Field(default_factory=list)
    claims: list = Field(default_factory=list)  # list[Claim]
    overall_status: ReportStatus = ReportStatus.PARTIAL


# ─── Prediction ───────────────────────────────────────────────────────────────

class PredictionFactor(BaseModel):
    feature: str
    contribution: float
    direction: str  # positive | negative


class Prediction(BaseModel):
    prediction_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    model: str
    model_version: str
    window: PredictionWindow
    score: float = Field(ge=0.0, le=1.0)
    band: RiskBand
    top_factors: list[PredictionFactor] = Field(default_factory=list)
    claims: list = Field(default_factory=list)  # list[Claim]
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    feature_snapshot: dict = Field(default_factory=dict)


# ─── Knowledge Pack ───────────────────────────────────────────────────────────

class KnowledgeChunk(BaseModel):
    chunk_id: str
    text: str
    embedding: list[float] | None = None
    metadata: dict = Field(default_factory=dict)


class KnowledgeDoc(BaseModel):
    knowledge_doc_id: UUID = Field(default_factory=uuid4)
    title: str
    source: str  # WHO | MinSante-RDC | UpToDate
    version: str
    date: date
    license: str
    language: str = "fr"
    chunks: list[KnowledgeChunk] = Field(default_factory=list)
