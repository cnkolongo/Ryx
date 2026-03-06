"""EncounterRow — ORM SQLAlchemy."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from ..database import Base


class EncounterRow(Base):
    __tablename__ = "encounters"

    encounter_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_type: Mapped[str] = mapped_column(String(32), nullable=False, default="outpatient")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["PatientRow"] = relationship("PatientRow", back_populates="encounters")
    lab_results: Mapped[list["LabResultRow"]] = relationship(
        "LabResultRow", back_populates="encounter"
    )

    def __repr__(self) -> str:
        return f"<Encounter {self.encounter_id} patient={self.patient_id} type={self.encounter_type}>"
