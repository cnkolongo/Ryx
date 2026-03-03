"""MedGemmaAgent — Synthèse clinique + claims avec MedGemma 1.5."""

import asyncio
import uuid
import json
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig, RyxMode
from ryx_shared.claims import Claim, ClaimType, CriticalityLevel, ClaimStatus
from ryx_shared.models import Report, ReportSections

logger = structlog.get_logger(__name__)


MEDGEMMA_SYSTEM_PROMPT = """
Tu es RYX, un assistant clinique de soutien au médecin (PAS un médecin).
Tu dois TOUJOURS :
1. Séparer clairement "contexte patient" (données du dossier) et "connaissance générale" (guidelines)
2. Citer la source exacte pour chaque claim (document, lab, image, ou knowledge)
3. Dire explicitement quand les données sont insuffisantes
4. NE JAMAIS inventer ou supposer des valeurs cliniques

Format de réponse : JSON structuré selon le schema Report.
"""


class MedGemmaAgent:
    """
    Écoute : preprocess.completed (+ optionnel pillar0.completed)
    Fait : synthèse clinique + questions + alertes → claims PENDING
    Publie : medgemma.completed

    Routing :
    - Hub : MedGemma 1.5 complet (HuggingFace)
    - Edge : MedGemma ONNX quantisé (int8/int4)
    """

    TOPIC = "preprocess.completed"
    GROUP = "medgemma-agent-group"

    def __init__(self, event_bus: EventBus, config: RyxConfig):
        self.event_bus = event_bus
        self.config = config
        self.instance_id = f"medgemma-{uuid.uuid4().hex[:8]}"
        self.running = False
        self._model = None  # chargé au premier appel

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("medgemma_agent.started", instance=self.instance_id, mode=self.config.ryx_mode)

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("medgemma_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        doc_id = event.payload.get("doc_id")
        patient_id = event.payload.get("patient_id")

        logger.info("medgemma_agent.processing", doc_id=doc_id, patient_id=patient_id)

        # TODO: récupérer contexte complet depuis DB
        context = await self._build_context(patient_id, doc_id)

        # TODO: générer le rapport avec MedGemma
        report, claims = await self._generate_report(context, patient_id)

        await self.event_bus.publish(
            "medgemma.completed",
            {
                "report_id": str(report.report_id),
                "patient_id": patient_id,
                "claims": [c.model_dump(mode="json") for c in claims],
                "job_id": event.payload.get("job_id"),
            },
            source="inference",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    async def _build_context(self, patient_id: str, doc_id: str) -> dict:
        """Assembler le contexte patient pour MedGemma."""
        # TODO: récupérer depuis DB
        # - historique encounters
        # - labs récents
        # - findings imagerie
        # - médicaments actifs
        return {
            "patient_id": patient_id,
            "doc_id": doc_id,
            "encounters": [],
            "labs": [],
            "findings": [],
        }

    async def _generate_report(
        self, context: dict, patient_id: str
    ) -> tuple[Report, list[Claim]]:
        """Générer rapport + claims avec MedGemma."""
        from ryx_shared.models import Report, ReportSections

        # TODO: appeler MedGemma (hub ou edge selon mode)
        report = Report(
            encounter_id=uuid.uuid4(),
            patient_id=uuid.UUID(patient_id) if isinstance(patient_id, str) else patient_id,
            model_version="medgemma-1.5-placeholder",
            sections=ReportSections(
                summary="Synthèse en attente d'implémentation MedGemma",
            ),
        )
        claims: list[Claim] = []
        return report, claims

    def _is_edge_mode(self) -> bool:
        return self.config.is_edge
