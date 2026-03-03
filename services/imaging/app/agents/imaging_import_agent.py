"""ImagingImportAgent — Import DICOM dans Orthanc + trigger Pillar-0."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus

logger = structlog.get_logger(__name__)


class ImagingImportAgent:
    """
    Écoute : ingestion.received (type=imaging/dicom)
    Fait : import DICOM dans Orthanc, extraire metadata, thumbnail
    Publie : imaging.imported
    """

    TOPIC = "ingestion.received"
    GROUP = "imaging-import-group"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.instance_id = f"imaging-import-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info("imaging_import_agent.started")

        while self.running:
            try:
                messages = await self.event_bus.consume(
                    self.TOPIC, self.GROUP, self.instance_id
                )
                for msg_id, event in messages:
                    # Ne traiter que les documents DICOM
                    if event.payload.get("document_type") == "imaging":
                        await self._process(msg_id, event)
                    else:
                        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
            except Exception as e:
                logger.error("imaging_import_agent.error", error=str(e))
                await asyncio.sleep(5)

    async def _process(self, msg_id: str, event):
        doc_id = event.payload.get("doc_id")
        patient_id = event.payload.get("patient_id")
        storage_path = event.payload.get("storage_path")

        logger.info("imaging_import_agent.importing", doc_id=doc_id)

        # TODO: télécharger DICOM depuis MinIO + importer dans Orthanc
        study_id = str(uuid.uuid4())  # placeholder

        await self.event_bus.publish(
            "imaging.imported",
            {
                "study_id": study_id,
                "patient_id": patient_id,
                "doc_id": doc_id,
                "modality": "CT",  # TODO: extraire depuis DICOM header
                "orthanc_study_id": f"orthanc-{uuid.uuid4().hex[:8]}",
            },
            source="imaging",
            correlation_id=event.correlation_id,
        )
        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
