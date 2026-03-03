"""EvidenceRef — Preuves cliquables (PDF, DICOM, Lab, Knowledge)."""

from datetime import datetime
from typing import Literal, Annotated, Union
from uuid import UUID

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Coordonnées normalisées [0.0, 1.0] pour bbox dans un document."""
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)


class DocEvidenceRef(BaseModel):
    """Preuve dans un document PDF ou image (avec bbox)."""
    kind: Literal["doc"] = "doc"
    doc_id: UUID
    page: int = Field(ge=1)
    bbox: BoundingBox
    snippet_text: str
    confidence: float = Field(ge=0.0, le=1.0)


class DicomEvidenceRef(BaseModel):
    """Preuve dans une étude DICOM (slice + ROI)."""
    kind: Literal["dicom"] = "dicom"
    study_id: UUID
    series_id: str
    instance_or_slice: str
    roi: BoundingBox | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class LabEvidenceRef(BaseModel):
    """Preuve dans un résultat de laboratoire."""
    kind: Literal["lab"] = "lab"
    lab_id: UUID
    test: str
    value: float | str
    unit: str | None = None
    date: datetime
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeEvidenceRef(BaseModel):
    """Preuve dans le Knowledge Pack (guidelines, protocoles)."""
    kind: Literal["knowledge"] = "knowledge"
    knowledge_doc_id: UUID
    chunk_id: str
    excerpt: str
    title: str | None = None  # titre du document source
    source: str | None = None  # WHO, MinSante-RDC, etc.
    confidence: float = Field(ge=0.0, le=1.0)


# Union discriminée sur `kind`
EvidenceRef = Annotated[
    Union[DocEvidenceRef, DicomEvidenceRef, LabEvidenceRef, KnowledgeEvidenceRef],
    Field(discriminator="kind")
]
