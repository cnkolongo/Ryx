"""IndexerAgent — Mise à jour index patient + Knowledge Pack dans Meilisearch."""

import asyncio
import uuid
import structlog
import httpx

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig

from ..meilisearch_client import index_patient

logger = structlog.get_logger(__name__)
config = RyxConfig()


class IndexerAgent:
    """
    Écoute : evidence.validate.completed
    Fait : update index Meilisearch (patient) avec claims validés
    Publie : index.update.completed

    OFFLINE-COMPATIBLE : Meilisearch tourne en local en mode edge.
    """

    TOPIC = "evidence.validate.completed"
    GROUP = "indexer-agent-group"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"indexer-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("indexer_agent.started", instance=self.instance_id)

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id, block_ms=1000
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("indexer_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        patient_id = event.payload.get("patient_id")
        report_id = event.payload.get("report_id")
        valid_claims = event.payload.get("valid_claims", [])

        logger.info(
            "indexer_agent.indexing",
            patient_id=patient_id,
            report_id=report_id,
            claims_count=len(valid_claims),
        )

        patient_doc = await self._build_patient_doc(patient_id, valid_claims)
        if patient_doc:
            try:
                await index_patient(patient_doc)
                logger.info("indexer_agent.patient_indexed", patient_id=patient_id)
            except Exception as e:
                logger.error(
                    "indexer_agent.index_error",
                    patient_id=patient_id,
                    error=str(e),
                )

        await self.event_bus.publish(
            "index.update.completed",
            {"patient_id": patient_id, "report_id": report_id},
            source="search",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    async def _build_patient_doc(
        self, patient_id: str | None, valid_claims: list
    ) -> dict | None:
        """Fetch patient from patient service and build Meilisearch document."""
        if not patient_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(
                    f"{config.patient_service_url}/v1/patients/{patient_id}"
                )
                if resp.status_code != 200:
                    logger.warning(
                        "indexer_agent.patient_fetch_failed",
                        patient_id=patient_id,
                        status=resp.status_code,
                    )
                    return None
                patient = resp.json()
        except Exception as e:
            logger.warning(
                "indexer_agent.patient_fetch_error",
                patient_id=patient_id,
                error=str(e),
            )
            return None

        demographics = patient.get("demographics") or {}
        claim_texts = [c.get("text", "") for c in valid_claims if c.get("text")]

        return {
            "patient_id": patient_id,
            "last_name": demographics.get("last_name", ""),
            "first_name": demographics.get("first_name", ""),
            "mrn": patient.get("mrn", ""),
            "phone": demographics.get("phone", ""),
            "gender": demographics.get("gender", ""),
            "date_of_birth": demographics.get("date_of_birth", ""),
            "claim_texts": claim_texts,
            "last_seen_at": patient.get("updated_at", ""),
        }
