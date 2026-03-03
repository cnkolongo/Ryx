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
        Télécharger les fichiers DICOM d'une étude depuis Orthanc.

        Orthanc REST API :
          GET /studies/{id}/instances  → liste des instance IDs
          GET /instances/{id}/file     → fichier .dcm brut
        Les fichiers sont mis en cache dans /tmp/ryx-dicom/{study_id}/.
        """
        import httpx
        from pathlib import Path

        orthanc_url = self.config.orthanc_url.rstrip("/")
        auth = (self.config.orthanc_username, self.config.orthanc_password)

        # Dossier de cache local
        cache_dir = Path(f"/tmp/ryx-dicom/{study_id}")
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Vérifier si déjà téléchargé (idempotence entre redémarrages)
        existing = sorted(cache_dir.glob("*.dcm"))
        if existing:
            logger.info(
                "pillar0_agent.dicom_cache_hit",
                study_id=study_id,
                count=len(existing),
            )
            return [str(p) for p in existing]

        async with httpx.AsyncClient(auth=auth, timeout=60.0) as client:
            # 1. Récupérer la liste des instances DICOM de l'étude
            resp = await client.get(f"{orthanc_url}/studies/{study_id}/instances")
            resp.raise_for_status()
            instances = resp.json()

            if not instances:
                logger.warning(
                    "pillar0_agent.dicom_no_instances",
                    study_id=study_id,
                    orthanc_url=orthanc_url,
                )
                return []

            logger.info(
                "pillar0_agent.dicom_downloading",
                study_id=study_id,
                instance_count=len(instances),
            )

            # 2. Télécharger chaque instance .dcm
            paths = []
            for i, instance in enumerate(instances):
                instance_id = instance["ID"]
                dest = cache_dir / f"{i:04d}_{instance_id}.dcm"

                if not dest.exists():
                    file_resp = await client.get(
                        f"{orthanc_url}/instances/{instance_id}/file"
                    )
                    file_resp.raise_for_status()
                    dest.write_bytes(file_resp.content)

                paths.append(str(dest))

            # Trier par nom de fichier → ordre de slice correct
            paths.sort()
            logger.info(
                "pillar0_agent.dicom_downloaded",
                study_id=study_id,
                count=len(paths),
                cache_dir=str(cache_dir),
            )
            return paths

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
        from ..store.job_queue import EdgeJobQueue

        queue = EdgeJobQueue()
        job_id = await queue.enqueue(
            job_type="pillar0",
            payload={
                "study_id": study_id,
                "modality": event.payload.get("modality"),
                "body_part": event.payload.get("body_part"),
                "correlation_id": event.correlation_id,
                "original_job_id": event.payload.get("job_id"),
            },
        )
        logger.info(
            "pillar0_agent.queued_for_hub",
            study_id=study_id,
            queue_job_id=job_id,
        )
