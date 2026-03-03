"""Claims — Assertions RYX (recommandations, alertes, scores, diagnostics)."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .evidence import EvidenceRef


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
    PENDING = "pending"        # En attente de validation EvidenceGuard
    VALID = "valid"            # Validé par EvidenceGuard
    BLOCKED = "blocked"        # Bloqué : preuve insuffisante
    NEEDS_HUMAN = "needs_human"  # Escalade vers clinicien


class Claim(BaseModel):
    """
    Assertion RYX. DOIT avoir evidence_refs pour être valide.

    Règle EvidenceGuard :
    - evidence_refs.length >= 1 OBLIGATOIRE pour status=valid
    - Si claim touche patient → au moins un ref kind in (doc, dicom, lab)
    - Si claim purement documentaire → ref kind == knowledge
    """

    claim_id: UUID = Field(default_factory=uuid4)
    type: ClaimType
    text: str = Field(min_length=1)
    criticality: CriticalityLevel
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.PENDING
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    validated_at: datetime | None = None
    validated_by: str | None = None  # "evidence_guard" | user_id

    @model_validator(mode="after")
    def check_valid_has_evidence(self) -> "Claim":
        """Un claim VALID ne peut pas avoir evidence_refs vide."""
        if self.status == ClaimStatus.VALID and len(self.evidence_refs) == 0:
            raise ValueError(
                "A VALID claim must have at least one evidence_ref. "
                "Use status=BLOCKED if no evidence is available."
            )
        return self

    def block(self, reason: str) -> "Claim":
        """Bloquer ce claim (immutable pattern — retourne nouvelle instance)."""
        return self.model_copy(update={
            "status": ClaimStatus.BLOCKED,
            "blocked_reason": reason,
            "validated_at": datetime.utcnow(),
            "validated_by": "evidence_guard",
        })

    def validate_claim(self, validated_by: str = "evidence_guard") -> "Claim":
        """Valider ce claim."""
        return self.model_copy(update={
            "status": ClaimStatus.VALID,
            "validated_at": datetime.utcnow(),
            "validated_by": validated_by,
        })

    def escalate(self, reason: str) -> "Claim":
        """Escalader vers clinicien."""
        return self.model_copy(update={
            "status": ClaimStatus.NEEDS_HUMAN,
            "blocked_reason": reason,
        })

    @property
    def has_patient_evidence(self) -> bool:
        """True si au moins une preuve patient (doc, dicom, lab)."""
        return any(ref.kind in ("doc", "dicom", "lab") for ref in self.evidence_refs)

    @property
    def has_knowledge_evidence(self) -> bool:
        """True si au moins une preuve documentaire (knowledge)."""
        return any(ref.kind == "knowledge" for ref in self.evidence_refs)
