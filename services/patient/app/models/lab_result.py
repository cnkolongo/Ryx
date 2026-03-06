"""LabResultRow — ORM SQLAlchemy."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from ..database import Base


class LabResultRow(Base):
    __tablename__ = "lab_results"

    lab_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    encounter_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("encounters.encounter_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    test: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # value peut être numérique ou textuelle (ex: "positif")
    value_numeric: Mapped[float | None] = mapped_column(Numeric(precision=12, scale=4), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_range: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    extracted_by: Mapped[str] = mapped_column(String(32), nullable=False, default="ocr")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    patient: Mapped["PatientRow"] = relationship("PatientRow", back_populates="lab_results")
    encounter: Mapped["EncounterRow"] = relationship("EncounterRow", back_populates="lab_results")
