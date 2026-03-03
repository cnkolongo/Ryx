"""IntegrationSyncAgent — Sync périodique avec les DMI externes."""

import asyncio
import uuid
import structlog
from datetime import datetime

from ryx_shared.events import EventBus
from ryx_connector_sdk import ConnectorRegistry, ConnectorMode

logger = structlog.get_logger(__name__)


class IntegrationSyncAgent:
    """
    Écoute : integration.sync.requested + schedule (toutes les heures)
    Fait : pull patients/encounters/docs depuis chaque connecteur configuré
    Publie : integration.sync.completed

    Modes :
    - shadow → lecture seule
    - link → mapping IDs uniquement
    - write-back → push rapports/alertes vers DMI
    """

    TOPIC = "integration.sync.requested"
    GROUP = "integration-sync-group"
    SYNC_INTERVAL = 3600  # 1 heure

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"integration-sync-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.registry = ConnectorRegistry()

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("integration_sync_agent.started")

        # Loop mixte : events + schedule
        while self.running:
            try:
                # Écouter les sync demandées
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id, block_ms=5000
                )
                for msg_id, event in messages:
                    connector_id = event.payload.get("connector_id")
                    await self._sync_connector(connector_id)
                    await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

            except Exception as e:
                logger.error("integration_sync_agent.error", error=str(e))
                await asyncio.sleep(10)

    async def _sync_connector(self, connector_id: str | None = None):
        """Sync un connecteur spécifique ou tous."""
        # TODO: implémenter sync réelle avec ConnectorRegistry
        logger.info("integration_sync_agent.syncing", connector_id=connector_id)

        await self.event_bus.publish(
            "integration.sync.completed",
            {
                "connector_id": connector_id or "all",
                "synced_at": datetime.utcnow().isoformat(),
                "patients_synced": 0,
                "encounters_synced": 0,
            },
            source="integration",
        )
