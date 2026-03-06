"""ClaimRow — ORM SQLAlchemy pour les claims RYX."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from ..database import Base


class ClaimRow(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    # Contexte clinique
    encounter_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    patient_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)

    # Données du claim
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    criticality: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Preuves (JSON array de EvidenceRef)
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Traçabilité
    validated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Claim {self.claim_id} type={self.type} status={self.status}>"
