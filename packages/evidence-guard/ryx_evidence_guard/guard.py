"""EvidenceGuard — Point d'entrée principal du policy engine."""

import structlog
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from ryx_shared.claims import Claim, ClaimStatus

from .rules import EvidenceGuardPolicy

logger = structlog.get_logger(__name__)


class ValidationAction(str, Enum):
    VALID = "valid"
    BLOCK = "block"
    ESCALATE = "escalate"  # needs_human


@dataclass
class ClaimValidationResult:
    claim_id: UUID
    valid: bool
    action: ValidationAction
    errors: list[str]
    warnings: list[str]
    validated_claim: Claim | None = None


class EvidenceGuard:
    """
    EvidenceGuard — Policy engine principal.

    Valide les claims selon les règles métier de RYX.
    Tout claim invalide est bloqué (status=BLOCKED).
    Principe : "Better empty than wrong".

    Usage :
        guard = EvidenceGuard()

        # Valider un claim
        result = guard.validate(claim)
        if result.valid:
            claim = result.validated_claim

        # Valider un batch
        results = guard.validate_batch(claims)
    """

    def __init__(self, policy: EvidenceGuardPolicy | None = None):
        self.policy = policy or EvidenceGuardPolicy()

    def validate(self, claim: Claim) -> ClaimValidationResult:
        """Valide un claim. Retourne le résultat avec claim mis à jour."""
        blocking_errors, warnings = self.policy.check(claim)

        if blocking_errors:
            blocked_reason = " | ".join(blocking_errors)
            validated_claim = claim.block(blocked_reason)
            action = ValidationAction.BLOCK

            logger.warning(
                "evidence_guard.claim_blocked",
                claim_id=str(claim.claim_id),
                claim_type=claim.type.value,
                criticality=claim.criticality.value,
                errors=blocking_errors,
            )

            return ClaimValidationResult(
                claim_id=claim.claim_id,
                valid=False,
                action=action,
                errors=blocking_errors,
                warnings=warnings,
                validated_claim=validated_claim,
            )

        validated_claim = claim.validate_claim()
        if warnings:
            logger.info(
                "evidence_guard.claim_validated_with_warnings",
                claim_id=str(claim.claim_id),
                warnings=warnings,
            )
        else:
            logger.info(
                "evidence_guard.claim_validated",
                claim_id=str(claim.claim_id),
                claim_type=claim.type.value,
            )

        return ClaimValidationResult(
            claim_id=claim.claim_id,
            valid=True,
            action=ValidationAction.VALID,
            errors=[],
            warnings=warnings,
            validated_claim=validated_claim,
        )

    def validate_batch(self, claims: list[Claim]) -> list[ClaimValidationResult]:
        """Valide un batch de claims. Tous sont traités indépendamment."""
        results = []
        for claim in claims:
            results.append(self.validate(claim))

        valid_count = sum(1 for r in results if r.valid)
        blocked_count = len(results) - valid_count
        logger.info(
            "evidence_guard.batch_completed",
            total=len(results),
            valid=valid_count,
            blocked=blocked_count,
        )
        return results

    def get_stats(self, results: list[ClaimValidationResult]) -> dict:
        return {
            "total": len(results),
            "valid": sum(1 for r in results if r.valid),
            "blocked": sum(1 for r in results if not r.valid),
            "with_warnings": sum(1 for r in results if r.warnings),
        }
