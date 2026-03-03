"""Pillar0Agent — Analyse CT/MRI avec Pillar-0 (vision 3D)."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig, RyxMode

logger = structlog.get_logger(__name__)


class Pillar0Agent:
    """
    Écoute : imaging.imported, pillar0.requested
    Fait : Pillar-0 vision 3D → findings + overlays + EvidenceRefs(dicom)
    Publie : pillar0.completed

    Routing :
    - edge mode + GPU dispo → run local (ONNX quantisé)
    - sinon → sérialiser job → queue hub → résultats téléchargés
    """

    TOPIC = "imaging.imported"
    GROUP = "pillar0-agent-group"

    def __init__(self, event_bus: EventBus, config: RyxConfig):
        self.event_bus = event_bus
        self.config = config
        self.instance_id = f"pillar0-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("pillar0_agent.started", instance=self.instance_id)

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("pillar0_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        study_id = event.payload.get("study_id")
        modality = event.payload.get("modality", "")

        # Pillar-0 ne traite que CT et MRI
        if modality not in ("CT", "MRI"):
            await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
            return

        logger.info("pillar0_agent.processing", study_id=study_id, modality=modality)

        if self._should_run_local():
            findings = await self._run_pillar0_local(study_id)
        else:
            # Différer vers hub (store & forward)
            await self._queue_for_hub(study_id, event)
            await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
            return

        await self.event_bus.publish(
            "pillar0.completed",
            {
                "study_id": study_id,
                "findings": findings,
                "job_id": event.payload.get("job_id"),
            },
            source="inference",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    def _should_run_local(self) -> bool:
        """Vérifier si GPU edge disponible."""
        if self.config.ryx_mode == RyxMode.HUB:
            return True
        # Edge : vérifier GPU
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def _run_pillar0_local(self, study_id: str) -> list[dict]:
        """
        Exécuter Pillar-0 en local.
        TODO: charger le modèle Pillar-0 et analyser les séries DICOM.
        """
        logger.info("pillar0_agent.running_local", study_id=study_id)
        # TODO: implémenter avec le vrai modèle Pillar-0
        return []

    async def _queue_for_hub(self, study_id: str, event):
        """Sérialiser le job pour traitement hub ultérieur."""
        logger.info("pillar0_agent.queued_for_hub", study_id=study_id)
        # TODO: stocker dans JobQueue locale (SQLite edge)
