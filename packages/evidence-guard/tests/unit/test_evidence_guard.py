"""Tests unitaires EvidenceGuard — cœur de la sécurité clinique RYX.

Couvre :
- Règle 1 : NO_EVIDENCE (tout claim doit avoir evidence_refs)
- Règle 2 : PATIENT_CLAIM_NO_PATIENT_EVIDENCE (reco/alert/dx/tx/score → doc/dicom/lab)
- Règle 3 : KNOWLEDGE_CLAIM_NO_KNOWLEDGE_EVIDENCE (info → knowledge ref)
- Règle 4 : LOW_CONFIDENCE (warning non-bloquant)
- validate_batch : comportement idempotent
- Cas limites : claims valides, claims multi-types, confidence exactement à la limite
"""

import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

import pytest

# Ajouter les packages au path
sys.path.insert(0, str(Path(__file__).parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[2]))

from ryx_shared.claims import Claim, ClaimType, CriticalityLevel, ClaimStatus
from ryx_shared.evidence import (
    DocEvidenceRef,
    LabEvidenceRef,
    DicomEvidenceRef,
    KnowledgeEvidenceRef,
    BoundingBox,
)
from ryx_evidence_guard import EvidenceGuard
from ryx_evidence_guard.rules import (
    EvidenceGuardPolicy,
    NoEvidenceRule,
    PatientClaimNeedsPatientEvidenceRule,
    KnowledgeClaimNeedsKnowledgeEvidenceRule,
    MinConfidenceRule,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_bbox() -> BoundingBox:
    return BoundingBox(x1=0.1, y1=0.1, x2=0.9, y2=0.9)


def doc_ref(confidence: float = 0.9) -> DocEvidenceRef:
    return DocEvidenceRef(
        doc_id=uuid4(), page=1, bbox=make_bbox(),
        snippet_text="Créatinine: 1.8 mg/dL", confidence=confidence
    )


def lab_ref(confidence: float = 0.9) -> LabEvidenceRef:
    return LabEvidenceRef(
        lab_id=uuid4(), test="creatinine", value=1.8, unit="mg/dL",
        date=datetime.utcnow(), confidence=confidence
    )


def dicom_ref(confidence: float = 0.9) -> DicomEvidenceRef:
    return DicomEvidenceRef(
        study_id=uuid4(), series_id="s1", instance_or_slice="42",
        confidence=confidence
    )


def knowledge_ref(confidence: float = 0.9) -> KnowledgeEvidenceRef:
    return KnowledgeEvidenceRef(
        knowledge_doc_id=uuid4(), chunk_id="c1",
        excerpt="Créatinine > 2.0 mg/dL indique insuffisance rénale",
        title="OMS Guidelines", source="WHO", confidence=confidence
    )


def make_claim(
    claim_type: ClaimType = ClaimType.ALERT,
    refs: list | None = None,
    criticality: CriticalityLevel = CriticalityLevel.HIGH,
) -> Claim:
    return Claim(
        claim_id=uuid4(),
        type=claim_type,
        text="Test claim",
        criticality=criticality,
        evidence_refs=refs if refs is not None else [],
    )


# ─── EvidenceGuard principal ──────────────────────────────────────────────────

class TestEvidenceGuardValidate:
    """Tests du point d'entrée EvidenceGuard.validate()."""

    def setup_method(self):
        self.guard = EvidenceGuard()

    def test_valid_alert_with_lab_ref(self):
        """Un claim ALERT avec lab_ref doit être validé."""
        claim = make_claim(ClaimType.ALERT, refs=[lab_ref()])
        result = self.guard.validate(claim)
        assert result.valid is True
        assert result.validated_claim is not None
        assert result.validated_claim.status == ClaimStatus.VALID
        assert result.errors == []

    def test_valid_reco_with_doc_ref(self):
        """Un claim RECO avec doc_ref doit être validé."""
        claim = make_claim(ClaimType.RECOMMENDATION, refs=[doc_ref()])
        result = self.guard.validate(claim)
        assert result.valid is True

    def test_valid_dx_with_dicom_ref(self):
        """Un claim DX avec dicom_ref doit être validé."""
        claim = make_claim(ClaimType.DIAGNOSIS, refs=[dicom_ref()])
        result = self.guard.validate(claim)
        assert result.valid is True

    def test_valid_info_with_knowledge_ref(self):
        """Un claim INFO avec knowledge_ref doit être validé."""
        claim = make_claim(ClaimType.INFO, refs=[knowledge_ref()])
        result = self.guard.validate(claim)
        assert result.valid is True

    def test_blocked_empty_evidence_refs(self):
        """Tout claim sans evidence_refs doit être bloqué — règle fondamentale."""
        claim = make_claim(ClaimType.ALERT, refs=[])
        result = self.guard.validate(claim)
        assert result.valid is False
        assert result.validated_claim is not None
        assert result.validated_claim.status == ClaimStatus.BLOCKED
        assert any("NO_EVIDENCE" in e for e in result.errors)

    def test_blocked_patient_claim_only_knowledge_ref(self):
        """Un claim ALERT avec seulement knowledge_ref doit être bloqué."""
        claim = make_claim(ClaimType.ALERT, refs=[knowledge_ref()])
        result = self.guard.validate(claim)
        assert result.valid is False
        assert any("PATIENT_CLAIM_NO_PATIENT_EVIDENCE" in e for e in result.errors)

    def test_blocked_info_claim_only_doc_ref(self):
        """Un claim INFO avec seulement doc_ref doit être bloqué."""
        claim = make_claim(ClaimType.INFO, refs=[doc_ref()])
        result = self.guard.validate(claim)
        assert result.valid is False
        assert any("KNOWLEDGE_CLAIM_NO_KNOWLEDGE_EVIDENCE" in e for e in result.errors)

    def test_warning_low_confidence_not_blocking(self):
        """Confidence faible → warning mais pas bloquant (MVP)."""
        claim = make_claim(ClaimType.ALERT, refs=[lab_ref(confidence=0.1)])
        result = self.guard.validate(claim)
        assert result.valid is True  # non-bloquant en MVP
        assert result.warnings != []
        assert any("LOW_CONFIDENCE" in w for w in result.warnings)

    def test_confidence_exactly_at_threshold_no_warning(self):
        """Confidence exactement à 0.3 → pas de warning."""
        claim = make_claim(ClaimType.ALERT, refs=[lab_ref(confidence=0.3)])
        result = self.guard.validate(claim)
        assert "LOW_CONFIDENCE" not in " ".join(result.warnings)

    def test_multiple_refs_mixed_valid(self):
        """Claim avec doc_ref + knowledge_ref → valide."""
        claim = make_claim(ClaimType.RECOMMENDATION, refs=[doc_ref(), knowledge_ref()])
        result = self.guard.validate(claim)
        assert result.valid is True

    def test_blocked_claim_has_blocked_reason(self):
        """Un claim bloqué doit avoir un blocked_reason."""
        claim = make_claim(ClaimType.ALERT, refs=[])
        result = self.guard.validate(claim)
        assert result.validated_claim is not None
        assert result.validated_claim.blocked_reason is not None
        assert len(result.validated_claim.blocked_reason) > 0

    def test_blocked_claim_has_validated_at(self):
        """Un claim bloqué doit avoir validated_at renseigné."""
        claim = make_claim(ClaimType.ALERT, refs=[])
        result = self.guard.validate(claim)
        assert result.validated_claim.validated_at is not None
        assert result.validated_claim.validated_by == "evidence_guard"

    def test_valid_claim_immutable_input(self):
        """validate() ne doit pas modifier le claim d'entrée (immutable pattern)."""
        claim = make_claim(ClaimType.ALERT, refs=[lab_ref()])
        original_status = claim.status
        self.guard.validate(claim)
        assert claim.status == original_status  # pas modifié


# ─── validate_batch ───────────────────────────────────────────────────────────

class TestEvidenceGuardBatch:
    """Tests de validate_batch."""

    def setup_method(self):
        self.guard = EvidenceGuard()

    def test_batch_all_valid(self):
        claims = [make_claim(ClaimType.ALERT, refs=[lab_ref()]) for _ in range(3)]
        results = self.guard.validate_batch(claims)
        assert len(results) == 3
        assert all(r.valid for r in results)

    def test_batch_all_blocked(self):
        claims = [make_claim(ClaimType.ALERT, refs=[]) for _ in range(3)]
        results = self.guard.validate_batch(claims)
        assert all(not r.valid for r in results)

    def test_batch_mixed(self):
        claims = [
            make_claim(ClaimType.ALERT, refs=[lab_ref()]),
            make_claim(ClaimType.ALERT, refs=[]),           # bloqué
            make_claim(ClaimType.INFO, refs=[knowledge_ref()]),
            make_claim(ClaimType.INFO, refs=[doc_ref()]),   # bloqué
        ]
        results = self.guard.validate_batch(claims)
        assert len(results) == 4
        valid = [r for r in results if r.valid]
        blocked = [r for r in results if not r.valid]
        assert len(valid) == 2
        assert len(blocked) == 2

    def test_batch_empty(self):
        results = self.guard.validate_batch([])
        assert results == []

    def test_batch_independent(self):
        """Chaque claim est traité indépendamment — un bloqué n'affecte pas les autres."""
        claims = [
            make_claim(ClaimType.ALERT, refs=[]),       # bloqué
            make_claim(ClaimType.ALERT, refs=[lab_ref()]),  # valide
        ]
        results = self.guard.validate_batch(claims)
        assert results[0].valid is False
        assert results[1].valid is True

    def test_get_stats(self):
        claims = [
            make_claim(ClaimType.ALERT, refs=[lab_ref()]),
            make_claim(ClaimType.ALERT, refs=[]),
            make_claim(ClaimType.ALERT, refs=[lab_ref(confidence=0.1)]),  # warning
        ]
        results = self.guard.validate_batch(claims)
        stats = self.guard.get_stats(results)
        assert stats["total"] == 3
        assert stats["valid"] == 2
        assert stats["blocked"] == 1
        assert stats["with_warnings"] == 1


# ─── Règles individuelles ─────────────────────────────────────────────────────

class TestNoEvidenceRule:
    def setup_method(self):
        self.rule = NoEvidenceRule()

    def test_blocks_empty_refs(self):
        claim = make_claim(refs=[])
        errors = self.rule.check(claim)
        assert len(errors) == 1
        assert "NO_EVIDENCE" in errors[0]

    def test_passes_with_any_ref(self):
        for ref in [doc_ref(), lab_ref(), dicom_ref(), knowledge_ref()]:
            claim = make_claim(refs=[ref])
            assert self.rule.check(claim) == []


class TestPatientClaimNeedsPatientEvidenceRule:
    def setup_method(self):
        self.rule = PatientClaimNeedsPatientEvidenceRule()

    @pytest.mark.parametrize("claim_type", [
        ClaimType.RECOMMENDATION, ClaimType.ALERT,
        ClaimType.DIAGNOSIS, ClaimType.TREATMENT, ClaimType.SCORE,
    ])
    def test_blocks_patient_claim_with_only_knowledge(self, claim_type):
        claim = make_claim(claim_type, refs=[knowledge_ref()])
        errors = self.rule.check(claim)
        assert len(errors) == 1
        assert "PATIENT_CLAIM_NO_PATIENT_EVIDENCE" in errors[0]

    @pytest.mark.parametrize("ref_fn", [doc_ref, lab_ref, dicom_ref])
    def test_passes_patient_claim_with_patient_ref(self, ref_fn):
        claim = make_claim(ClaimType.ALERT, refs=[ref_fn()])
        assert self.rule.check(claim) == []

    def test_info_claim_not_checked(self):
        """La règle ne s'applique pas aux claims INFO."""
        claim = make_claim(ClaimType.INFO, refs=[knowledge_ref()])
        assert self.rule.check(claim) == []

    def test_passes_with_mixed_refs(self):
        """Claim avec doc_ref + knowledge_ref → OK."""
        claim = make_claim(ClaimType.ALERT, refs=[doc_ref(), knowledge_ref()])
        assert self.rule.check(claim) == []


class TestKnowledgeClaimNeedsKnowledgeEvidenceRule:
    def setup_method(self):
        self.rule = KnowledgeClaimNeedsKnowledgeEvidenceRule()

    def test_blocks_info_with_only_doc_ref(self):
        claim = make_claim(ClaimType.INFO, refs=[doc_ref()])
        errors = self.rule.check(claim)
        assert "KNOWLEDGE_CLAIM_NO_KNOWLEDGE_EVIDENCE" in errors[0]

    def test_passes_info_with_knowledge_ref(self):
        claim = make_claim(ClaimType.INFO, refs=[knowledge_ref()])
        assert self.rule.check(claim) == []

    def test_non_info_claim_not_checked(self):
        """La règle ne s'applique qu'à INFO."""
        for t in [ClaimType.ALERT, ClaimType.RECOMMENDATION, ClaimType.DIAGNOSIS]:
            claim = make_claim(t, refs=[doc_ref()])
            assert self.rule.check(claim) == []


class TestMinConfidenceRule:
    def setup_method(self):
        self.rule = MinConfidenceRule(min_confidence=0.3)

    def test_warning_below_threshold(self):
        claim = make_claim(refs=[lab_ref(confidence=0.1)])
        warnings = self.rule.check(claim)
        assert len(warnings) == 1
        assert "LOW_CONFIDENCE" in warnings[0]

    def test_no_warning_above_threshold(self):
        claim = make_claim(refs=[lab_ref(confidence=0.8)])
        assert self.rule.check(claim) == []

    def test_no_warning_exactly_at_threshold(self):
        claim = make_claim(refs=[lab_ref(confidence=0.3)])
        assert self.rule.check(claim) == []

    def test_multiple_low_confidence_refs(self):
        claim = make_claim(refs=[lab_ref(confidence=0.1), doc_ref(confidence=0.2)])
        warnings = self.rule.check(claim)
        assert len(warnings) == 2


# ─── Cas métier spécifiques RDC ───────────────────────────────────────────────

class TestRDCClinicalCases:
    """Cas cliniques réels pour les contextes RDC (paludisme, malnutrition, etc.)."""

    def setup_method(self):
        self.guard = EvidenceGuard()

    def test_malaria_alert_requires_lab_evidence(self):
        """Alerte paludisme doit avoir résultat labo (TDR ou frottis)."""
        tdr_ref = LabEvidenceRef(
            lab_id=uuid4(), test="tdr_paludisme", value="positif",
            date=datetime.utcnow(), confidence=0.95
        )
        claim = Claim(
            claim_id=uuid4(),
            type=ClaimType.ALERT,
            text="TDR paludisme positif — traitement antipaludéen recommandé",
            criticality=CriticalityLevel.HIGH,
            evidence_refs=[tdr_ref],
        )
        result = self.guard.validate(claim)
        assert result.valid is True

    def test_malnutrition_score_blocked_without_evidence(self):
        """Score malnutrition sans mesures → bloqué."""
        claim = Claim(
            claim_id=uuid4(),
            type=ClaimType.SCORE,
            text="Score MUAC critique",
            criticality=CriticalityLevel.CRITICAL,
            evidence_refs=[],
        )
        result = self.guard.validate(claim)
        assert result.valid is False
        assert result.validated_claim.status == ClaimStatus.BLOCKED

    def test_treatment_requires_diagnosis_evidence(self):
        """Une prescription de traitement doit avoir une preuve patient."""
        claim = Claim(
            claim_id=uuid4(),
            type=ClaimType.TREATMENT,
            text="Administrer Artemether-Lumefantrine 80/480mg",
            criticality=CriticalityLevel.HIGH,
            evidence_refs=[knowledge_ref()],  # seulement guideline, pas patient
        )
        result = self.guard.validate(claim)
        assert result.valid is False  # pas de preuve patient
