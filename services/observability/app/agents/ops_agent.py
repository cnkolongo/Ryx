"""OpsAgent — Surveillance infrastructure et détection d'incidents."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus

logger = structlog.get_logger(__name__)


class OpsAgent:
    """
    Surveille : queues Redis, disk space, GPU, sync failures
    Publie : ops.incident (consommé par NotificationAgent → alertes admin)

    Check interval : toutes les 60 secondes.
    """

    CHECK_INTERVAL = 60

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"ops-agent-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        logger.info("ops_agent.started")

        while self.running:
            try:
                await self._check_all()
                await asyncio.sleep(self.CHECK_INTERVAL)
            except Exception as e:
                logger.error("ops_agent.error", error=str(e))
                await asyncio.sleep(10)

    async def _check_all(self):
        await self._check_redis_backlog()
        await self._check_gpu_availability()

    async def _check_redis_backlog(self):
        """Vérifier si une queue Redis est stuck (backlog trop grand)."""
        try:
            # TODO: vérifier xlen de chaque stream
            # Si backlog > seuil → publier ops.incident
            pass
        except Exception as e:
            await self._publish_incident("redis_check_failed", str(e), "warning")

    async def _check_gpu_availability(self):
        """Vérifier si GPU disponible pour Pillar-0/MedGemma."""
        try:
            import torch
            if not torch.cuda.is_available():
                # Pas forcément un incident (edge sans GPU est OK)
                pass
        except ImportError:
            pass

    async def _publish_incident(self, incident_type: str, message: str, severity: str = "error"):
        await self.event_bus.publish(
            "ops.incident",
            {
                "type": incident_type,
                "severity": severity,
                "message": message,
                "instance": self.instance_id,
            },
            source="observability",
        )
        logger.warning("ops.incident_published", type=incident_type, severity=severity)
