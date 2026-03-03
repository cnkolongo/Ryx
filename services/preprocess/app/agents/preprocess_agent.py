"""PreprocessAgent — OCR + nettoyage + extraction pour chaque document ingéré."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig
from ryx_shared.models import OcrBlock, BoundingBox

from ..ocr import run_ocr
from ..extractor import extract_labs, extract_vitals

logger = structlog.get_logger(__name__)
config = RyxConfig()


class PreprocessAgent:
    """
    Écoute : ingestion.received
    Fait : OCR + cleaning + extraction labs/constantes
    Publie : preprocess.completed
    """

    TOPIC = "ingestion.received"
    GROUP = "preprocess-agent-group"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"preprocess-agent-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("preprocess_agent.started", instance=self.instance_id)

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    await self._process(msg_id, event)
            except Exception as e:
                logger.error("preprocess_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        """Traiter un document : OCR + extraction + quality score."""
        doc_id = event.payload.get("doc_id")
        patient_id = event.payload.get("patient_id")
        storage_path = event.payload.get("storage_path")

        logger.info("preprocess_agent.processing", doc_id=doc_id)

        try:
            # 1. Télécharger depuis MinIO
            # file_data = await download_from_minio(storage_path)

            # 2. OCR
            # ocr_blocks = await run_ocr(file_data)
            ocr_blocks: list[OcrBlock] = []  # TODO

            # 3. Quality scoring
            quality_score = self._compute_quality_score(ocr_blocks)
            rescan_needed = quality_score < 0.3

            # 4. Extraction
            # labs = await extract_labs(ocr_blocks)
            # vitals = await extract_vitals(ocr_blocks)

            # 5. Sauvegarder en DB
            # await save_ocr_results(doc_id, ocr_blocks, quality_score)

            # 6. Publier preprocess.completed
            await self.event_bus.publish(
                "preprocess.completed",
                {
                    "doc_id": doc_id,
                    "patient_id": patient_id,
                    "quality_score": quality_score,
                    "rescan_needed": rescan_needed,
                    "ocr_blocks_count": len(ocr_blocks),
                    "job_id": event.payload.get("job_id"),
                },
                source="preprocess",
                correlation_id=event.correlation_id,
            )

            await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
            logger.info(
                "preprocess_agent.completed",
                doc_id=doc_id,
                quality_score=quality_score,
                rescan_needed=rescan_needed,
            )

        except Exception as e:
            logger.error("preprocess_agent.processing_failed", doc_id=doc_id, error=str(e))
            # TODO: retry logic

    def _compute_quality_score(self, ocr_blocks: list) -> float:
        """Calcule un score de qualité basé sur les blocs OCR."""
        if not ocr_blocks:
            return 0.0
        avg_confidence = sum(b.confidence for b in ocr_blocks) / len(ocr_blocks)
        return avg_confidence
