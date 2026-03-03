"""IndexerAgent — Mise à jour index patient + Knowledge Pack."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus

logger = structlog.get_logger(__name__)


class IndexerAgent:
    """
    Écoute : evidence.validate.completed
    Fait : update index Meilisearch (patient + knowledge)
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
        logger.info("indexer_agent.started")

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("indexer_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        patient_id = event.payload.get("patient_id")
        report_id = event.payload.get("report_id")

        logger.info("indexer_agent.indexing", patient_id=patient_id, report_id=report_id)

        # TODO: implémenter indexation Meilisearch
        # 1. Récupérer patient timeline depuis DB
        # 2. Mettre à jour index patient Meilisearch
        # 3. Mettre à jour index knowledge si nouveau contenu

        await self.event_bus.publish(
            "index.update.completed",
            {"patient_id": patient_id, "report_id": report_id},
            source="search",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
