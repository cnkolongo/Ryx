"""PreprocessAgent — OCR + nettoyage + extraction pour chaque document ingéré."""

import asyncio
import io
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
    Fait : télécharge depuis MinIO, OCR, extraction labs/constantes
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
        """Traiter un document : télécharger, OCR, extraction, publier."""
        doc_id = event.payload.get("doc_id")
        patient_id = event.payload.get("patient_id")
        encounter_id = event.payload.get("encounter_id")
        storage_path = event.payload.get("storage_path")
        mime_type = event.payload.get("mime_type", "application/pdf")

        logger.info("preprocess_agent.processing", doc_id=doc_id)

        try:
            # 1. Télécharger depuis MinIO
            file_data = await self._download_from_minio(storage_path)

            # 2. OCR
            if mime_type == "application/dicom":
                # DICOM → routing vers imaging service, pas OCR
                ocr_blocks: list[OcrBlock] = []
                await self.event_bus.publish(
                    "imaging.imported",
                    {
                        "doc_id": doc_id,
                        "patient_id": patient_id,
                        "encounter_id": encounter_id,
                        "storage_path": storage_path,
                        "job_id": event.payload.get("job_id"),
                    },
                    source="preprocess",
                    correlation_id=event.correlation_id,
                )
            else:
                ocr_blocks = await run_ocr(file_data, mime_type)

            # 3. Quality scoring
            quality_score = self._compute_quality_score(ocr_blocks)
            rescan_needed = quality_score < 0.3

            # 4. Extraction labs + vitaux
            labs = await extract_labs(ocr_blocks)
            vitals = await extract_vitals(ocr_blocks)

            logger.info(
                "preprocess_agent.extracted",
                doc_id=doc_id,
                ocr_blocks=len(ocr_blocks),
                labs=len(labs),
                vitals=len(vitals),
                quality_score=quality_score,
            )

            # 5. Publier preprocess.completed → déclenche MedGemmaAgent
            await self.event_bus.publish(
                "preprocess.completed",
                {
                    "doc_id": doc_id,
                    "patient_id": patient_id,
                    "encounter_id": encounter_id,
                    "quality_score": quality_score,
                    "rescan_needed": rescan_needed,
                    "ocr_blocks_count": len(ocr_blocks),
                    "ocr_blocks": [b.model_dump() for b in ocr_blocks[:200]],  # max 200 blocs
                    "extracted_labs": labs,
                    "extracted_vitals": vitals,
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
            )

        except Exception as e:
            logger.error("preprocess_agent.processing_failed", doc_id=doc_id, error=str(e))
            # Nack → Dead Letter Queue après 3 tentatives
            await self.event_bus.nack_dead_letter(self.TOPIC, self.GROUP, msg_id)

    async def _download_from_minio(self, storage_path: str) -> bytes:
        """Télécharger un document depuis MinIO."""
        from minio import Minio
        client = Minio(
            config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )
        # storage_path = "bucket/patient_id/doc_id/filename"
        parts = storage_path.split("/", 1)
        bucket = parts[0]
        object_name = parts[1] if len(parts) > 1 else storage_path

        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    def _compute_quality_score(self, ocr_blocks: list) -> float:
        if not ocr_blocks:
            return 0.0
        avg_confidence = sum(b.confidence for b in ocr_blocks) / len(ocr_blocks)
        return avg_confidence
