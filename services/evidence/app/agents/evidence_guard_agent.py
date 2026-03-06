"""EvidenceGuardAgent — Valide tous les claims avant publication."""

import asyncio
import uuid
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from ryx_shared.events import EventBus
from ryx_shared.claims import Claim, ClaimStatus
from ryx_evidence_guard import EvidenceGuard

from ..database import AsyncSessionLocal
from ..models.claim import ClaimRow

logger = structlog.get_logger(__name__)
guard = EvidenceGuard()


class EvidenceGuardAgent:
    """
    Écoute : medgemma.completed, prediction.completed
    Fait : valider tous les claims (EvidenceGuard policy) + persister en DB
    Publie : evidence.validate.completed | evidence.blocked

    SLA cible : < 1s par claim (in-memory policy engine)
    Principe : "Better empty than wrong"
    """

    GROUP = "evidence-guard-group"
    TOPICS = ["medgemma.completed", "prediction.completed"]

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"evidence-guard-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        for topic in self.TOPICS:
            await self.event_bus.ensure_consumer_group(topic, self.GROUP)
        logger.info("evidence_guard_agent.started", instance=self.instance_id)

        while self.running:
            try:
                for topic in self.TOPICS:
                    messages = await self.event_bus.consume(
                        topic, self.GROUP, self.instance_id, block_ms=1000
                    )
                    for msg_id, event in messages:
                        await self._process(msg_id, event, topic)
            except Exception as e:
                logger.error("evidence_guard_agent.error", error=str(e))
                await asyncio.sleep(2)

    async def _process(self, msg_id: str, event, topic: str):
        """Valider batch de claims depuis un event + persister en DB."""
        report_id = event.payload.get("report_id") or event.payload.get("prediction_id")
        patient_id = event.payload.get("patient_id")
        encounter_id = event.payload.get("encounter_id")
        raw_claims = event.payload.get("claims", [])

        if not raw_claims:
            await self.event_bus.ack(topic, self.GROUP, msg_id)
            return

        # Désérialiser et valider les claims
        claims = [Claim.model_validate(c) for c in raw_claims]
        results = guard.validate_batch(claims)
        stats = guard.get_stats(results)

        logger.info(
            "evidence_guard_agent.batch_validated",
            report_id=report_id,
            **stats,
        )

        # Persister tous les claims en DB
        async with AsyncSessionLocal() as db:
            for result in results:
                if result.validated_claim is None:
                    continue
                claim = result.validated_claim
                row = ClaimRow(
                    claim_id=str(claim.claim_id),
                    encounter_id=encounter_id,
                    patient_id=patient_id,
                    report_id=report_id,
                    type=claim.type.value,
                    text=claim.text,
                    criticality=claim.criticality.value,
                    status=claim.status.value,
                    blocked_reason=claim.blocked_reason,
                    evidence_refs=[
                        ref.model_dump(mode="json") for ref in claim.evidence_refs
                    ],
                    validated_by=claim.validated_by,
                    validated_at=claim.validated_at,
                )
                db.add(row)
            await db.commit()

        # Publier events pour les claims bloqués
        for result in [r for r in results if not r.valid]:
            await self.event_bus.publish(
                "evidence.blocked",
                {
                    "claim_id": str(result.claim_id),
                    "reason": " | ".join(result.errors),
                    "report_id": report_id,
                },
                source="evidence",
                correlation_id=event.correlation_id,
            )

        # Publier validation completed
        valid_claims = [r.validated_claim for r in results if r.valid and r.validated_claim]
        await self.event_bus.publish(
            "evidence.validate.completed",
            {
                "report_id": report_id,
                "patient_id": patient_id,
                "valid_count": stats["valid"],
                "blocked_count": stats["blocked"],
                "valid_claims": [c.model_dump(mode="json") for c in valid_claims],
                "job_id": event.payload.get("job_id"),
            },
            source="evidence",
            correlation_id=event.correlation_id,
        )

        await self.event_bus.ack(topic, self.GROUP, msg_id)
