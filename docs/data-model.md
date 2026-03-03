# RYX — Modèle de données

> Schémas Pydantic + SQL. Source de vérité pour tous les services.

---

## 1. Entités principales

### Patient
```python
class Patient(BaseModel):
    patient_id: UUID
    demographics: Demographics | None = None  # optionnel (données fragmentées)
    identifiers: list[Identifier] = []  # numéros locaux, noms, etc.
    external_ids: list[ExternalId] = []  # IDs dans DMI externes
    quality_flags: list[str] = []  # ex: "no_dob", "approximate_age"
    created_at: datetime
    updated_at: datetime

class Demographics(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    dob_approximate: bool = False
    sex: str | None = None  # M | F | Unknown
    phone: str | None = None
    address: str | None = None

class Identifier(BaseModel):
    type: str  # "national_id" | "patient_number" | "name_phonetic" | ...
    value: str
    issuer: str | None = None

class ExternalId(BaseModel):
    system: str  # "openmrs" | "dhis2" | "fhir" | "csv_import" | ...
    value: str
    linked_at: datetime
```

### Encounter
```python
class Encounter(BaseModel):
    encounter_id: UUID
    patient_id: UUID
    start_at: datetime
    end_at: datetime | None = None
    service: str | None = None  # "urgences" | "consultation" | "hospitalisation"
    reason: str | None = None
    location: str | None = None  # hôpital, service
    encounter_type: EncounterType  # inpatient | outpatient | emergency
    status: EncounterStatus  # active | completed | cancelled
    created_by: UUID  # user_id
    created_at: datetime
```

### Document
```python
class Document(BaseModel):
    doc_id: UUID
    encounter_id: UUID
    patient_id: UUID
    type: DocumentType  # lab_report | imaging | clinical_note | prescription | other
    original_filename: str | None = None
    mime_type: str  # application/pdf | image/jpeg | image/png | ...
    storage_path: str  # MinIO path
    pages: int | None = None
    quality_score: float | None = None  # 0.0 à 1.0
    rescan_needed: bool = False
    ocr_blocks: list[OcrBlock] = []
    language: str | None = None  # fr | en | ...
    created_at: datetime
    preprocessed_at: datetime | None = None

class OcrBlock(BaseModel):
    block_id: str
    page: int
    bbox: BoundingBox  # x1, y1, x2, y2 (coordonnées normalisées 0-1)
    text: str
    confidence: float  # 0.0 à 1.0
    block_type: str  # "paragraph" | "table" | "header" | "value"
```

### LabResult
```python
class LabResult(BaseModel):
    lab_id: UUID
    encounter_id: UUID
    patient_id: UUID
    document_id: UUID | None = None  # source document si extrait par OCR
    test: str  # "créatinine" | "hémoglobine" | etc.
    value: float | str  # valeur numérique ou textuelle
    unit: str | None = None
    ref_range: ReferenceRange | None = None
    date: datetime
    status: LabStatus  # normal | abnormal | critical | unknown
    extracted_by: str  # "ocr" | "clinician" | "connector"

class ReferenceRange(BaseModel):
    low: float | None = None
    high: float | None = None
    text: str | None = None  # ex: "< 0.5 mg/L"
```

### ImagingStudy
```python
class ImagingStudy(BaseModel):
    study_id: UUID
    encounter_id: UUID
    patient_id: UUID
    orthanc_study_id: str  # ID dans Orthanc
    modality: str  # CT | MRI | CXR | ECG | ...
    body_part: str | None = None
    date: datetime
    series: list[ImagingSeries] = []
    pillar0_status: JobStatus | None = None

class ImagingSeries(BaseModel):
    series_id: str
    orthanc_series_id: str
    description: str | None = None
    instances_count: int
```

### Finding
```python
class Finding(BaseModel):
    finding_id: UUID
    patient_id: UUID
    encounter_id: UUID | None = None
    source: FindingSource  # pillar0 | ocr | clinician
    label: str  # ex: "consolidation pulmonaire"
    severity: str | None = None  # mild | moderate | severe | critical
    time: datetime
    evidence_refs: list[EvidenceRef]
    clinician_confirmed: bool | None = None
    clinician_note: str | None = None
```

### Report
```python
class Report(BaseModel):
    report_id: UUID
    encounter_id: UUID
    patient_id: UUID
    generated_at: datetime
    model_version: str  # version MedGemma utilisée
    sections: ReportSections
    recommendations: list[Claim] = []
    questions: list[str] = []  # questions à poser au patient
    claims: list[Claim] = []
    overall_status: ReportStatus  # complete | partial | blocked

class ReportSections(BaseModel):
    summary: str | None = None
    timeline: str | None = None
    labs_trend: str | None = None
    imaging_findings: str | None = None
    active_problems: list[str] = []
    medications: list[str] = []
```

### Prediction
```python
class Prediction(BaseModel):
    prediction_id: UUID
    patient_id: UUID
    model: str  # nom du plugin
    model_version: str
    window: PredictionWindow  # 30d | 6m | 1y | 2y
    score: float  # 0.0 à 1.0
    band: RiskBand  # low | moderate | high | critical
    top_factors: list[PredictionFactor]
    claims: list[Claim]
    computed_at: datetime
    feature_snapshot: dict  # FeatureTimeline sérialisée

class PredictionFactor(BaseModel):
    feature: str
    contribution: float  # SHAP value ou équivalent
    direction: str  # "positive" | "negative"

class PredictionWindow(str, Enum):
    D30 = "30d"
    M6 = "6m"
    Y1 = "1y"
    Y2 = "2y"
```

### KnowledgeDoc
```python
class KnowledgeDoc(BaseModel):
    knowledge_doc_id: UUID
    title: str
    source: str  # "WHO" | "MinSante-RDC" | "UpToDate" | ...
    version: str
    date: date
    license: str
    language: str
    chunks: list[KnowledgeChunk] = []

class KnowledgeChunk(BaseModel):
    chunk_id: str
    text: str
    embedding: list[float] | None = None  # vecteur pour similarity search
    metadata: dict = {}
```

---

## 2. EvidenceRef — Preuve cliquable

```python
from typing import Literal, Union
from pydantic import BaseModel, UUID4

class BoundingBox(BaseModel):
    x1: float  # 0.0 à 1.0 (normalisé)
    y1: float
    x2: float
    y2: float

class DocEvidenceRef(BaseModel):
    kind: Literal["doc"] = "doc"
    doc_id: UUID
    page: int
    bbox: BoundingBox
    snippet_text: str
    confidence: float  # 0.0 à 1.0

class DicomEvidenceRef(BaseModel):
    kind: Literal["dicom"] = "dicom"
    study_id: UUID
    series_id: str
    instance_or_slice: str
    roi: BoundingBox | None = None
    confidence: float

class LabEvidenceRef(BaseModel):
    kind: Literal["lab"] = "lab"
    lab_id: UUID
    test: str
    value: float | str
    unit: str | None = None
    date: datetime
    confidence: float

class KnowledgeEvidenceRef(BaseModel):
    kind: Literal["knowledge"] = "knowledge"
    knowledge_doc_id: UUID
    chunk_id: str
    excerpt: str
    confidence: float

# Union type utilisé partout
EvidenceRef = Union[DocEvidenceRef, DicomEvidenceRef, LabEvidenceRef, KnowledgeEvidenceRef]
```

---

## 3. Claim — Le concept central

```python
class ClaimType(str, Enum):
    RECOMMENDATION = "reco"
    ALERT = "alert"
    SCORE = "score"
    DIAGNOSIS = "dx"
    TREATMENT = "tx"
    INFO = "info"

class CriticalityLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

class ClaimStatus(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"

class Claim(BaseModel):
    claim_id: UUID
    type: ClaimType
    text: str
    criticality: CriticalityLevel
    evidence_refs: list[EvidenceRef]  # DOIT être non-vide pour être VALID
    status: ClaimStatus = ClaimStatus.PENDING
    blocked_reason: str | None = None
    created_at: datetime
    validated_at: datetime | None = None
    validated_by: str | None = None  # "evidence_guard" | user_id

    @model_validator(mode="after")
    def validate_evidence(self) -> "Claim":
        """EvidenceGuard inline : bloque si aucune preuve"""
        if self.status == ClaimStatus.VALID and len(self.evidence_refs) == 0:
            raise ValueError("A valid claim must have at least one evidence_ref")
        return self
```

---

## 4. Job (idempotence + retry)

```python
class JobType(str, Enum):
    PREPROCESS = "preprocess"
    PILLAR0 = "pillar0"
    MEDGEMMA = "medgemma"
    PREDICTION = "prediction"
    EVIDENCE_VALIDATE = "evidence_validate"
    INDEX_UPDATE = "index_update"
    INTEGRATION_SYNC = "integration_sync"
    NOTIFICATION = "notification"

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"

class JobLocation(str, Enum):
    EDGE = "edge"
    HUB = "hub"

class Job(BaseModel):
    job_id: UUID
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    payload: dict  # job-specific data
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None
    location: JobLocation = JobLocation.HUB
    priority: int = 5  # 1 (highest) to 10 (lowest)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

---

## 5. Events (Redis Streams)

```python
# Format standard d'un event
class RyxEvent(BaseModel):
    event_id: str  # généré automatiquement
    topic: str  # ex: "ingestion.received"
    version: str = "1.0"
    timestamp: datetime
    payload: dict
    source_service: str
    correlation_id: str | None = None  # pour tracer un pipeline complet

# Events définis
TOPICS = {
    # Ingestion pipeline
    "ingestion.received": {"doc_id": "uuid", "patient_id": "uuid", "type": "str"},
    "preprocess.completed": {"doc_id": "uuid", "quality_score": "float", "rescan_needed": "bool"},
    "imaging.imported": {"study_id": "uuid", "modality": "str"},

    # AI pipeline
    "pillar0.requested": {"study_id": "uuid", "job_id": "uuid"},
    "pillar0.completed": {"study_id": "uuid", "findings": "list", "job_id": "uuid"},
    "medgemma.requested": {"encounter_id": "uuid", "job_id": "uuid"},
    "medgemma.completed": {"report_id": "uuid", "claims": "list", "job_id": "uuid"},
    "prediction.requested": {"patient_id": "uuid", "window": "str", "job_id": "uuid"},
    "prediction.completed": {"prediction_id": "uuid", "job_id": "uuid"},

    # Evidence pipeline
    "evidence.validate.requested": {"claim_ids": "list"},
    "evidence.validate.completed": {"report_id": "uuid", "valid_count": "int", "blocked_count": "int"},
    "evidence.blocked": {"claim_id": "uuid", "reason": "str"},

    # Post-processing
    "index.update.requested": {"patient_id": "uuid", "doc_ids": "list"},
    "index.update.completed": {"patient_id": "uuid"},
    "integration.sync.requested": {"connector_id": "str", "since": "datetime"},
    "integration.sync.completed": {"connector_id": "str", "synced_count": "int"},
    "notify.requested": {"alert_ids": "list", "channels": "list"},
    "notify.sent": {"notification_id": "uuid", "channel": "str"},

    # Ops
    "ops.incident": {"type": "str", "severity": "str", "message": "str"},
}
```

---

## 6. Schéma SQL (PostgreSQL)

```sql
-- Patients
CREATE TABLE patients (
    patient_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demographics    JSONB,
    identifiers     JSONB NOT NULL DEFAULT '[]',
    external_ids    JSONB NOT NULL DEFAULT '[]',
    quality_flags   TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Encounters
CREATE TABLE encounters (
    encounter_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(patient_id),
    start_at        TIMESTAMPTZ NOT NULL,
    end_at          TIMESTAMPTZ,
    service         TEXT,
    reason          TEXT,
    location        TEXT,
    encounter_type  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    created_by      UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_encounters_patient ON encounters(patient_id);
CREATE INDEX idx_encounters_start ON encounters(start_at DESC);

-- Documents
CREATE TABLE documents (
    doc_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id    UUID NOT NULL REFERENCES encounters(encounter_id),
    patient_id      UUID NOT NULL REFERENCES patients(patient_id),
    type            TEXT NOT NULL,
    original_filename TEXT,
    mime_type       TEXT NOT NULL,
    storage_path    TEXT NOT NULL,
    pages           INT,
    quality_score   FLOAT,
    rescan_needed   BOOLEAN DEFAULT FALSE,
    ocr_blocks      JSONB NOT NULL DEFAULT '[]',
    language        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    preprocessed_at TIMESTAMPTZ
);
CREATE INDEX idx_documents_encounter ON documents(encounter_id);
CREATE INDEX idx_documents_patient ON documents(patient_id);

-- Lab Results
CREATE TABLE lab_results (
    lab_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id    UUID NOT NULL REFERENCES encounters(encounter_id),
    patient_id      UUID NOT NULL REFERENCES patients(patient_id),
    document_id     UUID REFERENCES documents(doc_id),
    test            TEXT NOT NULL,
    value_text      TEXT,
    value_numeric   FLOAT,
    unit            TEXT,
    ref_range       JSONB,
    date            TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'unknown',
    extracted_by    TEXT NOT NULL
);
CREATE INDEX idx_labs_patient_date ON lab_results(patient_id, date DESC);
CREATE INDEX idx_labs_test ON lab_results(test);

-- Claims (coeur EvidenceGuard)
CREATE TABLE claims (
    claim_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id       UUID,
    prediction_id   UUID,
    type            TEXT NOT NULL,
    text            TEXT NOT NULL,
    criticality     TEXT NOT NULL,
    evidence_refs   JSONB NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'pending',
    blocked_reason  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at    TIMESTAMPTZ,
    validated_by    TEXT
);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_report ON claims(report_id) WHERE report_id IS NOT NULL;

-- Jobs
CREATE TABLE jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    payload         JSONB NOT NULL,
    retry_count     INT NOT NULL DEFAULT 0,
    max_retries     INT NOT NULL DEFAULT 3,
    last_error      TEXT,
    location        TEXT NOT NULL DEFAULT 'hub',
    priority        INT NOT NULL DEFAULT 5,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_jobs_status_priority ON jobs(status, priority) WHERE status = 'queued';
CREATE INDEX idx_jobs_type ON jobs(type);

-- Audit Log
CREATE TABLE audit_logs (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID,
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_time ON audit_logs(created_at DESC);
```
