"""EvidenceGuard — Règles de validation des claims."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ryx_shared.claims import Claim, ClaimType


class PolicyRule(Protocol):
    """Interface pour une règle de validation."""

    def check(self, claim: Claim) -> list[str]:
        """Retourne liste d'erreurs (vide si OK)."""
        ...


@dataclass
class NoEvidenceRule:
    """Règle 1 : tout claim doit avoir au moins une preuve."""

    def check(self, claim: Claim) -> list[str]:
        if len(claim.evidence_refs) == 0:
            return ["NO_EVIDENCE: claim has no evidence_refs — 'better empty than wrong'"]
        return []


@dataclass
class PatientClaimNeedsPatientEvidenceRule:
    """
    Règle 2 : un claim qui touche le patient (reco, alert, dx, tx, score)
    doit avoir au moins un EvidenceRef de type doc, dicom ou lab.
    Un claim purement documentaire (info) peut n'avoir que knowledge refs.
    """

    PATIENT_CLAIM_TYPES = {
        ClaimType.RECOMMENDATION,
        ClaimType.ALERT,
        ClaimType.DIAGNOSIS,
        ClaimType.TREATMENT,
        ClaimType.SCORE,
    }

    def check(self, claim: Claim) -> list[str]:
        if claim.type not in self.PATIENT_CLAIM_TYPES:
            return []

        patient_refs = [r for r in claim.evidence_refs if r.kind in ("doc", "dicom", "lab")]
        if not patient_refs:
            return [
                f"PATIENT_CLAIM_NO_PATIENT_EVIDENCE: "
                f"claim type={claim.type.value} requires at least one "
                f"doc/dicom/lab evidence_ref (found: {[r.kind for r in claim.evidence_refs]})"
            ]
        return []


@dataclass
class KnowledgeClaimNeedsKnowledgeEvidenceRule:
    """
    Règle 3 : un claim purement documentaire/apprentissage (info)
    doit avoir au moins un EvidenceRef de type knowledge.
    """

    def check(self, claim: Claim) -> list[str]:
        if claim.type != ClaimType.INFO:
            return []

        knowledge_refs = [r for r in claim.evidence_refs if r.kind == "knowledge"]
        if not knowledge_refs:
            return [
                "KNOWLEDGE_CLAIM_NO_KNOWLEDGE_EVIDENCE: "
                "info claim requires at least one knowledge evidence_ref"
            ]
        return []


@dataclass
class MinConfidenceRule:
    """Règle 4 : confidence minimale pour les preuves critiques."""

    min_confidence: float = 0.3

    def check(self, claim: Claim) -> list[str]:
        errors = []
        for ref in claim.evidence_refs:
            if ref.confidence < self.min_confidence:
                errors.append(
                    f"LOW_CONFIDENCE: evidence_ref {ref.kind} "
                    f"has confidence={ref.confidence:.2f} < {self.min_confidence}"
                )
        return errors


class EvidenceGuardPolicy:
    """
    Policy engine RYX. Applique toutes les règles sur un claim.

    Règles actives :
    1. NoEvidenceRule — obligatoire
    2. PatientClaimNeedsPatientEvidenceRule — obligatoire
    3. KnowledgeClaimNeedsKnowledgeEvidenceRule — obligatoire
    4. MinConfidenceRule — warning (non-bloquant en MVP)
    """

    def __init__(self, min_confidence: float = 0.3):
        self.blocking_rules: list = [
            NoEvidenceRule(),
            PatientClaimNeedsPatientEvidenceRule(),
            KnowledgeClaimNeedsKnowledgeEvidenceRule(),
        ]
        self.warning_rules: list = [
            MinConfidenceRule(min_confidence=min_confidence),
        ]

    def check(self, claim: Claim) -> tuple[list[str], list[str]]:
        """
        Retourne (blocking_errors, warnings).
        Si blocking_errors non-vide → claim doit être bloqué.
        """
        blocking_errors: list[str] = []
        warnings: list[str] = []

        for rule in self.blocking_rules:
            blocking_errors.extend(rule.check(claim))

        for rule in self.warning_rules:
            warnings.extend(rule.check(claim))

        return blocking_errors, warnings
