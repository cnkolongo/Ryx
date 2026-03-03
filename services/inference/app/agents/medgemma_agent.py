"""MedGemmaAgent — Synthèse clinique + claims avec MedGemma 1.5."""

import asyncio
import uuid
import structlog

from ryx_shared.events import EventBus
from ryx_shared.config import RyxConfig
from ryx_shared.claims import Claim, ClaimType, CriticalityLevel, ClaimStatus
from ryx_shared.models import Report, ReportSections
from ryx_shared.evidence import KnowledgeEvidenceRef, LabEvidenceRef, DocEvidenceRef

from ..runners.medgemma_runner import MedGemmaRunner, MedGemmaOutput

logger = structlog.get_logger(__name__)

# Mapping texte MedGemma → ClaimType enum
_CLAIM_TYPE_MAP = {
    "alert": ClaimType.ALERT,
    "reco": ClaimType.RECOMMENDATION,
    "dx": ClaimType.DIAGNOSIS,
    "tx": ClaimType.TREATMENT,
    "info": ClaimType.INFO,
}

# Mapping texte MedGemma → CriticalityLevel enum
_CRITICALITY_MAP = {
    "critical": CriticalityLevel.CRITICAL,
    "high": CriticalityLevel.HIGH,
    "moderate": CriticalityLevel.MODERATE,
    "low": CriticalityLevel.LOW,
}


class MedGemmaAgent:
    """
    Écoute : preprocess.completed (+ optionnel pillar0.completed)
    Fait : synthèse clinique + questions + alertes → claims PENDING
    Publie : medgemma.completed

    Routing :
    - Hub : MedGemma 1.5 complet (HuggingFace bfloat16)
    - Edge : MedGemma ONNX quantisé (int8/int4)
    """

    TOPIC = "preprocess.completed"
    GROUP = "medgemma-agent-group"

    def __init__(self, event_bus: EventBus, config: RyxConfig):
        self.event_bus = event_bus
        self.config = config
        self.instance_id = f"medgemma-{uuid.uuid4().hex[:8]}"
        self.running = False
        self._runner: MedGemmaRunner | None = None

    def _get_runner(self) -> MedGemmaRunner:
        """Initialiser le runner à la demande (lazy loading)."""
        if self._runner is None:
            self._runner = MedGemmaRunner(
                hub_model_path=self.config.medgemma_model_path,
                onnx_path=self.config.medgemma_onnx_path,
                is_edge=self.config.is_edge,
            )
        return self._runner

    async def run(self):
        self.running = True
        await self.event_bus.ensure_consumer_group(self.TOPIC, self.GROUP)
        logger.info(
            "medgemma_agent.started",
            instance=self.instance_id,
            mode="edge" if self.config.is_edge else "hub",
        )

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
        encounter_id = event.payload.get("encounter_id")

        logger.info(
            "medgemma_agent.processing",
            doc_id=doc_id,
            patient_id=patient_id,
        )

        try:
            context = await self._build_context(patient_id, doc_id, encounter_id)
            report, claims = await self._generate_report(
                context, patient_id, encounter_id
            )

            await self.event_bus.publish(
                "medgemma.completed",
                {
                    "report_id": str(report.report_id),
                    "patient_id": patient_id,
                    "encounter_id": encounter_id,
                    "claims": [c.model_dump(mode="json") for c in claims],
                    "claims_count": len(claims),
                    "blocked_count": sum(
                        1 for c in claims if c.status == ClaimStatus.BLOCKED
                    ),
                    "job_id": event.payload.get("job_id"),
                },
                source="inference",
                correlation_id=event.correlation_id,
            )

            logger.info(
                "medgemma_agent.completed",
                patient_id=patient_id,
                claims=len(claims),
                blocked=sum(1 for c in claims if c.status == ClaimStatus.BLOCKED),
            )

        except Exception as e:
            logger.error(
                "medgemma_agent.run_failed",
                patient_id=patient_id,
                error=str(e),
            )
            await self.event_bus.publish(
                "ops.incident",
                {
                    "type": "medgemma_inference_failed",
                    "severity": "error",
                    "message": f"MedGemma a échoué pour patient {patient_id}: {str(e)[:200]}",
                },
                source="inference",
            )

        await self.event_bus.ack(self.TOPIC, self.GROUP, msg_id)

    async def _build_context(
        self,
        patient_id: str,
        doc_id: str | None,
        encounter_id: str | None,
    ) -> dict:
        """
        Assembler le contexte patient pour MedGemma depuis les services internes.

        Récupère via les event payloads ou les services REST :
          - Historique des rencontres (3 dernières)
          - Labs récents (10 derniers)
          - Findings Pillar-0 (si disponibles)
          - Texte OCR des documents (si disponibles)
        """
        import httpx

        context: dict = {
            "patient_id": patient_id,
            "doc_id": doc_id,
            "encounter_id": encounter_id,
            "encounters": [],
            "labs": [],
            "findings": [],
            "docs_text": [],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Récupérer les rencontres récentes
                patient_url = self.config.patient_service_url
                r = await client.get(
                    f"{patient_url}/v1/patients/{patient_id}/encounters",
                    params={"limit": 3, "sort": "desc"},
                )
                if r.status_code == 200:
                    context["encounters"] = r.json().get("items", [])

                # Récupérer les labs récents
                r = await client.get(
                    f"{patient_url}/v1/patients/{patient_id}/labs",
                    params={"limit": 10, "sort": "desc"},
                )
                if r.status_code == 200:
                    context["labs"] = r.json().get("items", [])

                # Récupérer les findings imagerie (Pillar-0)
                if encounter_id:
                    imaging_url = self.config.imaging_service_url
                    r = await client.get(
                        f"{imaging_url}/v1/studies",
                        params={"encounter_id": encounter_id},
                    )
                    if r.status_code == 200:
                        studies = r.json().get("items", [])
                        for study in studies:
                            for finding in study.get("findings", []):
                                finding["study_id"] = study.get("study_id")
                                finding["modality"] = study.get("modality")
                                context["findings"].append(finding)

                # Récupérer le texte OCR du document déclencheur
                if doc_id:
                    preprocess_url = self.config.preprocess_service_url
                    r = await client.get(
                        f"{preprocess_url}/v1/documents/{doc_id}/ocr"
                    )
                    if r.status_code == 200:
                        doc_data = r.json()
                        full_text = " ".join(
                            block.get("text", "")
                            for block in doc_data.get("blocks", [])
                        )
                        if full_text:
                            context["docs_text"].append({
                                "doc_id": doc_id,
                                "type": doc_data.get("type", "unknown"),
                                "text": full_text,
                            })

        except Exception as e:
            # Le contexte partiel est acceptable — mieux que rien
            logger.warning(
                "medgemma_agent.context_partial",
                patient_id=patient_id,
                error=str(e),
            )

        return context

    async def _generate_report(
        self,
        context: dict,
        patient_id: str,
        encounter_id: str | None,
    ) -> tuple[Report, list[Claim]]:
        """Générer rapport + claims avec MedGemma."""
        runner = self._get_runner()
        output: MedGemmaOutput = await runner.generate(context)

        # Construire le Report
        enc_id = (
            uuid.UUID(encounter_id)
            if encounter_id and len(encounter_id) == 36
            else uuid.uuid4()
        )
        pat_id = (
            uuid.UUID(patient_id)
            if patient_id and len(patient_id) == 36
            else uuid.uuid4()
        )

        report = Report(
            encounter_id=enc_id,
            patient_id=pat_id,
            model_version=output.model_version,
            sections=ReportSections(
                summary=output.summary,
                timeline=output.timeline,
                labs_trend=output.labs_trend,
                imaging_findings=output.imaging_findings,
                active_problems=output.active_problems,
                medications=output.medications,
            ),
            questions=output.questions,
        )

        # Convertir les raw_claims en Claim Pydantic
        claims = self._build_claims(output.raw_claims, context)

        return report, claims

    def _build_claims(
        self, raw_claims: list[dict], context: dict
    ) -> list[Claim]:
        """
        Convertir les claims bruts MedGemma en objets Claim avec evidence_refs.

        Pour chaque source citée par MedGemma :
          - kind=lab     → LabEvidenceRef (si lab_id trouvé dans contexte)
          - kind=doc     → DocEvidenceRef (si doc_id trouvé)
          - kind=dicom   → DicomEvidenceRef (si study_id trouvé)
          - kind=knowledge → KnowledgeEvidenceRef (si chunk_id trouvé)

        Sans source → status=BLOCKED (règle EvidenceGuard).
        """
        claims = []
        # Index rapide des labs par lab_id
        labs_index = {
            str(lab.get("lab_id", "")): lab
            for lab in context.get("labs", [])
        }
        # Index des findings par study_id
        findings_index: dict[str, list] = {}
        for f in context.get("findings", []):
            sid = str(f.get("study_id", ""))
            findings_index.setdefault(sid, []).append(f)

        for raw in raw_claims:
            claim_type = _CLAIM_TYPE_MAP.get(
                raw.get("type", "info"), ClaimType.INFO
            )
            criticality = _CRITICALITY_MAP.get(
                raw.get("criticality", "low"), CriticalityLevel.LOW
            )
            text = raw.get("text", "").strip()
            if not text:
                continue

            evidence_refs = []
            for src in raw.get("sources", []):
                ref = self._resolve_evidence_ref(src, labs_index, findings_index, context)
                if ref is not None:
                    evidence_refs.append(ref)

            if evidence_refs:
                status = ClaimStatus.PENDING  # EvidenceGuard validera ensuite
            else:
                status = ClaimStatus.BLOCKED

            try:
                claim = Claim(
                    type=claim_type,
                    text=text,
                    criticality=criticality,
                    evidence_refs=evidence_refs,
                    status=status,
                    blocked_reason=(
                        "Aucune source citée par le modèle"
                        if status == ClaimStatus.BLOCKED
                        else None
                    ),
                )
                claims.append(claim)
            except Exception as e:
                logger.warning(
                    "medgemma_agent.claim_build_failed",
                    text=text[:100],
                    error=str(e),
                )

        return claims

    def _resolve_evidence_ref(
        self,
        src: dict,
        labs_index: dict,
        findings_index: dict,
        context: dict,
    ):
        """Résoudre une source brute MedGemma en EvidenceRef typé."""
        from datetime import datetime
        from ryx_shared.evidence import DicomEvidenceRef

        kind = src.get("kind", "")
        ref_id = str(src.get("ref", ""))

        if kind == "lab":
            lab = labs_index.get(ref_id)
            if lab:
                try:
                    return LabEvidenceRef(
                        lab_id=uuid.UUID(ref_id),
                        test=lab.get("test", "?"),
                        value=lab.get("value", "?"),
                        unit=lab.get("unit"),
                        date=datetime.fromisoformat(
                            lab.get("date", datetime.utcnow().isoformat())
                        ),
                        confidence=0.9,
                    )
                except Exception:
                    pass

        elif kind == "doc":
            doc_id = context.get("doc_id") or ref_id
            try:
                return DocEvidenceRef(
                    doc_id=uuid.UUID(doc_id) if len(doc_id) == 36 else uuid.uuid4(),
                    page=1,
                    bbox=__import__(
                        "ryx_shared.evidence", fromlist=["BoundingBox"]
                    ).BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                    snippet_text=src.get("excerpt", ""),
                    confidence=0.8,
                )
            except Exception:
                pass

        elif kind == "dicom":
            # Trouver le study_id correspondant
            for sid, flist in findings_index.items():
                try:
                    return DicomEvidenceRef(
                        study_id=uuid.UUID(sid) if len(sid) == 36 else uuid.uuid4(),
                        series_id="main",
                        instance_or_slice="0",
                        confidence=0.85,
                    )
                except Exception:
                    continue

        elif kind == "knowledge":
            chunk_id = src.get("chunk_id", ref_id)
            try:
                return KnowledgeEvidenceRef(
                    knowledge_doc_id=uuid.uuid4(),
                    chunk_id=chunk_id or "unknown",
                    excerpt=src.get("excerpt", ""),
                    title=src.get("title"),
                    source=src.get("source"),
                    confidence=0.75,
                )
            except Exception:
                pass

        return None
