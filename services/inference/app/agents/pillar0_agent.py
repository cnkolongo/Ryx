"""Pillar0Agent — Analyse CT/MRI avec Pillar-0 (YalaLab, UC Berkeley/UCSF)."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig, RyxMode
from ryx_shared.evidence import DicomEvidenceRef, BoundingBox

from ..runners.pillar0_runner import Pillar0Runner, Pillar0Result, Pillar0Finding

logger = structlog.get_logger(__name__)

# Seuil de criticité pour publier une alerte
CRITICAL_FINDINGS = {
    "intracranial_hemorrhage", "subdural_hematoma", "epidural_hematoma",
    "subarachnoid_hemorrhage", "pulmonary_embolism", "pneumothorax",
    "aortic_aneurysm", "free_air", "midline_shift",
}


class Pillar0Agent:
    """
    Écoute : imaging.imported, pillar0.requested
    Fait : Pillar-0 → findings + EvidenceRefs(dicom) + overlays
    Publie : pillar0.completed

    Routing :
    - Hub ou edge avec GPU  → Pillar0Runner local (HuggingFace)
    - Edge sans GPU         → job sérialisé → hub (store & forward)
    """

    TOPIC = "imaging.imported"
    GROUP = "pillar0-agent-group"

    def __init__(self, event_bus: EventBus, config: RyxConfig):
        self.event_bus = event_bus
        self.config = config
        self.instance_id = f"pillar0-{uuid.uuid4().hex[:8]}"
        self.running = False
        self._runner: Pillar0Runner | None = None

    def _get_runner(self) -> Pillar0Runner:
        """Initialiser le runner à la demande (lazy loading)."""
        if self._runner is None:
            self._runner = Pillar0Runner(
                cache_dir=self.config.pillar0_model_path,
                confidence_threshold=0.5,
            )
        return self._runner

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
        body_part = event.payload.get("body_part")

        # Pillar-0 ne traite que CT et MRI
        if modality not in ("CT", "MR", "MRI"):
            await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)
            return

        logger.info("pillar0_agent.processing", study_id=study_id, modality=modality)

        if self._should_run_local():
            await self._run_and_publish(study_id, body_part, event)
        else:
            await self._queue_for_hub(study_id, event)

        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    async def _run_and_publish(self, study_id: str, body_part: str | None, event):
        """Lancer Pillar-0 localement et publier les résultats."""
        try:
            # Récupérer les chemins DICOM depuis Orthanc (via MinIO ou API)
            dicom_paths = await self._fetch_dicom_paths(study_id)

            result = await self._get_runner().analyze(
                dicom_paths=dicom_paths,
                study_id=study_id,
                body_part=body_part,
            )

            # Convertir les findings en EvidenceRefs DICOM
            evidence_refs = self._findings_to_evidence_refs(result, study_id)

            # Sérialiser pour l'event
            findings_payload = [
                {
                    "label": f.label,
                    "score": f.score,
                    "positive": f.positive,
                    "category": f.category,
                    "roi_slice": f.roi_slice,
                }
                for f in result.positive_findings
            ]

            await self.event_bus.publish(
                "pillar0.completed",
                {
                    "study_id": study_id,
                    "modality": result.modality.value,
                    "findings": findings_payload,
                    "evidence_refs": [e.model_dump(mode="json") for e in evidence_refs],
                    "positive_count": len(result.positive_findings),
                    "critical": any(
                        f.label in CRITICAL_FINDINGS for f in result.positive_findings
                    ),
                    "job_id": event.payload.get("job_id"),
                },
                source="inference",
                correlation_id=event.correlation_id,
            )

            logger.info(
                "pillar0_agent.completed",
                study_id=study_id,
                positive_findings=len(result.positive_findings),
                top=[f.label for f in result.positive_findings[:3]],
            )

        except Exception as e:
            logger.error("pillar0_agent.run_failed", study_id=study_id, error=str(e))
            # Publier l'erreur comme incident ops
            await self.event_bus.publish(
                "ops.incident",
                {
                    "type": "pillar0_inference_failed",
                    "severity": "error",
                    "message": f"Pillar-0 a échoué sur study {study_id}: {str(e)[:200]}",
                },
                source="inference",
            )

    def _findings_to_evidence_refs(
        self, result: Pillar0Result, study_id: str
    ) -> list[DicomEvidenceRef]:
        """
        Convertir Pillar0Finding → DicomEvidenceRef (preuves cliquables).
        Chaque finding positif devient une preuve avec slice index.
        """
        refs = []
        for finding in result.positive_findings:
            refs.append(DicomEvidenceRef(
                kind="dicom",
                study_id=uuid.UUID(study_id) if len(study_id) == 36 else uuid.uuid4(),
                series_id="main",  # TODO: récupérer le vrai series_id
                instance_or_slice=str(finding.roi_slice or 0),
                roi=BoundingBox(
                    x1=finding.roi_bbox[0] if finding.roi_bbox else 0.1,
                    y1=finding.roi_bbox[1] if finding.roi_bbox else 0.1,
                    x2=finding.roi_bbox[2] if finding.roi_bbox else 0.9,
                    y2=finding.roi_bbox[3] if finding.roi_bbox else 0.9,
                ) if finding.roi_bbox else None,
                confidence=finding.score,
            ))
        return refs

    async def _fetch_dicom_paths(self, study_id: str) -> list[str]:
        """
        Récupérer les chemins des fichiers DICOM depuis Orthanc.
        TODO: implémenter avec l'API REST Orthanc.
        """
        import httpx
        orthanc_url = self.config.orthanc_url
        auth = (self.config.orthanc_username, self.config.orthanc_password)

        # Télécharger les instances d'une étude depuis Orthanc
        # GET /studies/{id}/instances → liste des instance IDs
        # GET /instances/{id}/file   → fichier .dcm brut
        # TODO: télécharger dans /tmp et retourner les chemins locaux
        logger.warning("pillar0_agent.dicom_fetch_not_implemented", study_id=study_id)
        return []  # TODO

    def _should_run_local(self) -> bool:
        """Hub → toujours local. Edge → seulement si GPU disponible."""
        if self.config.ryx_mode == RyxMode.HUB:
            return True
        import torch
        return torch.cuda.is_available()

    async def _queue_for_hub(self, study_id: str, event):
        """
        Edge sans GPU : sérialiser le job pour traitement hub ultérieur.
        Stocké en SQLite local → sync dès que connectivité disponible.
        """
        logger.info("pillar0_agent.queued_for_hub", study_id=study_id)
        # TODO: persister dans JobQueue SQLite locale
        # from ..store.job_queue import EdgeJobQueue
        # await EdgeJobQueue.enqueue("pillar0", {"study_id": study_id, ...})
