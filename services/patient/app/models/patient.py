"""PatientRow — ORM SQLAlchemy."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy import JSON as JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from ..database import Base


class PatientRow(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    # Données démographiques stockées en JSON (flexibilité schema)
    demographics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    identifiers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    external_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    quality_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    encounters: Mapped[list["EncounterRow"]] = relationship(
        "EncounterRow", back_populates="patient", cascade="all, delete-orphan"
    )
    lab_results: Mapped[list["LabResultRow"]] = relationship(
        "LabResultRow", back_populates="patient", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        demo = self.demographics or {}
        return f"<Patient {self.patient_id} name={demo.get('last_name', '?')}>"
