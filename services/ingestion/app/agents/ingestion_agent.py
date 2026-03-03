"""IngestionAgent — Consomme les uploads et déclenche le preprocessing."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig

logger = structlog.get_logger(__name__)
config = RyxConfig()


class IngestionAgent:
    """
    Agent 24/7 qui :
    - Pull les nouveaux documents des connecteurs DMI (schedule)
    - Publie ingestion.received pour chaque nouveau document
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"ingestion-agent-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        """Loop principal 24/7."""
        self.running = True
        logger.info("ingestion_agent.started", instance=self.instance_id)

        while self.running:
            try:
                # TODO: pull depuis connecteurs DMI configurés
                await self._pull_from_connectors()
                await asyncio.sleep(60)  # polling toutes les minutes
            except Exception as e:
                logger.error("ingestion_agent.error", error=str(e))
                await asyncio.sleep(10)

    async def _pull_from_connectors(self):
        """Pull nouveaux documents depuis les connecteurs configurés."""
        # TODO: implémenter avec ConnectorRegistry
        pass

    async def stop(self):
        self.running = False
        logger.info("ingestion_agent.stopped", instance=self.instance_id)
