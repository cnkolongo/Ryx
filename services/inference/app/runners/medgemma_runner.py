"""
MedGemmaRunner — Inférence clinique avec MedGemma 1.5 (Google DeepMind).

Modes :
  Hub  : google/medgemma-4b-it via HuggingFace Transformers (bfloat16)
  Edge : modèle ONNX quantisé int8 via ONNX Runtime

Rôle :
  Prend en entrée un contexte patient structuré (docs OCR, labs, findings Pillar-0,
  historique rencontres) et génère :
    - Un Report (sections cliniques structurées)
    - Des Claims PENDING (alertes, recommandations, diagnostics) avec evidence_refs

Règle EvidenceGuard :
  Chaque claim généré doit avoir evidence_refs pointant vers les données source.
  Les claims sans evidence_refs sont émis avec status=BLOCKED.

Références :
  - HuggingFace : https://huggingface.co/google/medgemma-4b-it
  - Paper       : MedGemma (Google DeepMind, 2025)
"""

from __future__ import annotations

import asyncio
import functools
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# HuggingFace model ID
MEDGEMMA_HUB_MODEL_ID = "google/medgemma-4b-it"

# Prompt système — instruit MedGemma à rester dans le rôle d'assistant, pas médecin
SYSTEM_PROMPT = """Tu es RYX, assistant clinique d'aide à la décision (PAS un médecin).
Ton rôle : aider le clinicien à synthétiser l'information disponible.

RÈGLES ABSOLUES :
1. Chaque claim (alerte, recommandation, diagnostic, traitement) DOIT citer sa source.
   Format source : {"kind": "doc"|"dicom"|"lab"|"knowledge", "ref": "..."}
2. Si les données sont insuffisantes : dis-le explicitement, n'invente RIEN.
3. Sépare clairement "contexte patient" (données dossier) et "connaissance générale".
4. NE JAMAIS inventer des valeurs numériques (labs, scores, dates).
5. Réponds UNIQUEMENT en JSON selon le schéma fourni.

Schéma de réponse :
{
  "summary": "...",
  "timeline": "...",
  "labs_trend": "...",
  "imaging_findings": "...",
  "active_problems": ["..."],
  "medications": ["..."],
  "claims": [
    {
      "type": "alert"|"reco"|"dx"|"tx"|"info",
      "text": "...",
      "criticality": "low"|"moderate"|"high"|"critical",
      "sources": [{"kind": "doc"|"dicom"|"lab"|"knowledge", "ref": "..."}]
    }
  ],
  "questions": ["..."]
}"""


@dataclass
class MedGemmaOutput:
    """Résultat brut de l'inférence MedGemma avant conversion en models."""
    summary: str
    timeline: str | None
    labs_trend: str | None
    imaging_findings: str | None
    active_problems: list[str]
    medications: list[str]
    raw_claims: list[dict]
    questions: list[str]
    model_version: str


class MedGemmaRunner:
    """
    Runner MedGemma — gère hub (HuggingFace) et edge (ONNX) de façon transparente.

    Usage :
        runner = MedGemmaRunner(
            hub_model_path="/models/medgemma-1.5",
            onnx_path="/models/edge/medgemma-int8.onnx",
            is_edge=False,
        )
        output = await runner.generate(context)
    """

    def __init__(
        self,
        hub_model_path: str = "/models/medgemma-1.5",
        onnx_path: str = "/models/edge/medgemma-int8.onnx",
        is_edge: bool = False,
        device: str | None = None,
        max_new_tokens: int = 2048,
    ):
        self.hub_model_path = Path(hub_model_path)
        self.onnx_path = Path(onnx_path)
        self.is_edge = is_edge
        self.max_new_tokens = max_new_tokens

        self._model = None
        self._tokenizer = None
        self._onnx_session = None

        # Auto-détection GPU
        if device is None:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(
            "medgemma_runner.initialized",
            mode="edge" if is_edge else "hub",
            device=self.device,
        )

    async def load(self) -> None:
        """Charger le modèle (lazy — appelé au premier generate)."""
        if self.is_edge:
            await self._load_onnx()
        else:
            await self._load_hub()

    async def _load_hub(self) -> None:
        """Charger MedGemma depuis HuggingFace (ou cache local)."""
        if self._model is not None:
            return

        logger.info("medgemma_runner.loading_hub", model=MEDGEMMA_HUB_MODEL_ID)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_hub_sync)
        logger.info("medgemma_runner.hub_loaded", device=self.device)

    def _load_hub_sync(self) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        model_id = (
            str(self.hub_model_path)
            if self.hub_model_path.exists()
            else MEDGEMMA_HUB_MODEL_ID
        )

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=str(self.hub_model_path),
            trust_remote_code=True,
        )

        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=str(self.hub_model_path),
            torch_dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        if self.device != "cuda":
            self._model = self._model.to(self.device)
        self._model.eval()

    async def _load_onnx(self) -> None:
        """Charger le modèle ONNX quantisé pour edge."""
        if self._onnx_session is not None:
            return

        if not self.onnx_path.exists():
            logger.warning(
                "medgemma_runner.onnx_not_found",
                path=str(self.onnx_path),
                fallback="hub",
            )
            self.is_edge = False
            await self._load_hub()
            return

        logger.info("medgemma_runner.loading_onnx", path=str(self.onnx_path))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_onnx_sync)
        logger.info("medgemma_runner.onnx_loaded")

    def _load_onnx_sync(self) -> None:
        import onnxruntime as ort

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._onnx_session = ort.InferenceSession(
            str(self.onnx_path),
            providers=providers,
        )

    async def generate(self, context: dict[str, Any]) -> MedGemmaOutput:
        """
        Générer une synthèse clinique depuis le contexte patient.

        Args:
            context: dict avec clés :
              patient_id, encounters, labs, findings, docs_text, imaging_findings

        Returns:
            MedGemmaOutput avec sections + claims bruts
        """
        # Charger le modèle si nécessaire
        if self._model is None and self._onnx_session is None:
            await self.load()

        prompt = self._build_prompt(context)

        loop = asyncio.get_event_loop()
        if self.is_edge and self._onnx_session is not None:
            raw_text = await loop.run_in_executor(
                None,
                functools.partial(self._infer_onnx_sync, prompt),
            )
        else:
            raw_text = await loop.run_in_executor(
                None,
                functools.partial(self._infer_hub_sync, prompt),
            )

        output = self._parse_response(raw_text)
        logger.info(
            "medgemma_runner.generated",
            claims_count=len(output.raw_claims),
            problems_count=len(output.active_problems),
        )
        return output

    def _build_prompt(self, context: dict[str, Any]) -> str:
        """
        Construire le prompt MedGemma à partir du contexte patient.
        Formate les données cliniques en texte structuré.
        """
        parts = [SYSTEM_PROMPT, "\n\n## CONTEXTE PATIENT\n"]

        # Rencontres récentes
        encounters = context.get("encounters", [])
        if encounters:
            parts.append("### Rencontres récentes\n")
            for enc in encounters[-3:]:  # 3 dernières seulement
                parts.append(
                    f"- {enc.get('date', '?')} | {enc.get('type', '?')} | "
                    f"Motif: {enc.get('reason', 'non renseigné')}\n"
                )

        # Résultats de laboratoire
        labs = context.get("labs", [])
        if labs:
            parts.append("\n### Résultats de laboratoire\n")
            for lab in labs[-10:]:  # 10 plus récents
                status_tag = f" [{lab.get('status', '').upper()}]" if lab.get("status") not in ("normal", "unknown", "") else ""
                parts.append(
                    f"- {lab.get('test', '?')}: {lab.get('value', '?')} "
                    f"{lab.get('unit', '')} {status_tag} "
                    f"(ID: {lab.get('lab_id', '?')})\n"
                )

        # Findings imagerie Pillar-0
        findings = context.get("findings", [])
        if findings:
            parts.append("\n### Findings imagerie (Pillar-0)\n")
            for f in findings:
                parts.append(
                    f"- [{f.get('modality', 'CT')}] {f.get('label', '?')} "
                    f"(score: {f.get('score', 0):.2f}) "
                    f"| Study: {f.get('study_id', '?')}\n"
                )

        # Texte extrait des documents OCR
        docs_text = context.get("docs_text", [])
        if docs_text:
            parts.append("\n### Extraits documents\n")
            for doc in docs_text[:3]:  # 3 docs max
                parts.append(
                    f"Document {doc.get('doc_id', '?')} "
                    f"({doc.get('type', '?')}):\n"
                    f"{doc.get('text', '')[:800]}\n\n"  # limite 800 chars/doc
                )

        if not any([encounters, labs, findings, docs_text]):
            parts.append("Aucune donnée disponible dans le dossier.\n")

        parts.append(
            "\n\n## INSTRUCTION\n"
            "Génère la synthèse clinique au format JSON selon le schéma fourni. "
            "Chaque claim doit citer ses sources précisément. "
            "Si les données sont insuffisantes, indique-le dans summary.\n"
        )

        return "".join(parts)

    def _infer_hub_sync(self, prompt: str) -> str:
        """Inférence HuggingFace synchrone."""
        import torch

        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=4096,
        ).to(self.device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,        # déterministe — important en médical
                temperature=1.0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Décoder seulement les tokens générés (pas le prompt)
        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _infer_onnx_sync(self, prompt: str) -> str:
        """
        Inférence ONNX synchrone pour edge.
        Requiert un modèle ONNX exporté avec tokenizer inclus.
        """
        try:
            from transformers import AutoTokenizer
            # Tokenizer séparé pour ONNX (identique au hub)
            tokenizer = AutoTokenizer.from_pretrained(
                str(self.hub_model_path)
                if self.hub_model_path.exists()
                else MEDGEMMA_HUB_MODEL_ID,
            )
            inputs = tokenizer(
                prompt,
                return_tensors="np",
                truncation=True,
                max_length=2048,
            )
            outputs = self._onnx_session.run(
                None,
                {
                    "input_ids": inputs["input_ids"],
                    "attention_mask": inputs["attention_mask"],
                },
            )
            # outputs[0] = logits ou token ids selon export
            output_ids = outputs[0][0]
            return tokenizer.decode(output_ids, skip_special_tokens=True)
        except Exception as e:
            logger.error("medgemma_runner.onnx_infer_failed", error=str(e))
            return self._empty_response()

    def _parse_response(self, raw_text: str) -> MedGemmaOutput:
        """
        Parser la réponse JSON de MedGemma.
        Robuste aux réponses mal formées — fallback sur structure vide.
        """
        # Extraire le JSON de la réponse (parfois entouré de texte)
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if not json_match:
            logger.warning(
                "medgemma_runner.no_json_in_response",
                raw_preview=raw_text[:200],
            )
            return self._parse_empty()

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(
                "medgemma_runner.json_parse_error",
                error=str(e),
                raw_preview=raw_text[:200],
            )
            return self._parse_empty(summary=raw_text[:500])

        return MedGemmaOutput(
            summary=data.get("summary", "Synthèse non disponible"),
            timeline=data.get("timeline"),
            labs_trend=data.get("labs_trend"),
            imaging_findings=data.get("imaging_findings"),
            active_problems=data.get("active_problems", []),
            medications=data.get("medications", []),
            raw_claims=data.get("claims", []),
            questions=data.get("questions", []),
            model_version=MEDGEMMA_HUB_MODEL_ID,
        )

    def _parse_empty(self, summary: str = "") -> MedGemmaOutput:
        return MedGemmaOutput(
            summary=summary or "Données insuffisantes pour générer une synthèse.",
            timeline=None,
            labs_trend=None,
            imaging_findings=None,
            active_problems=[],
            medications=[],
            raw_claims=[],
            questions=[],
            model_version=MEDGEMMA_HUB_MODEL_ID,
        )

    def _empty_response(self) -> str:
        return json.dumps({
            "summary": "Erreur d'inférence ONNX — données insuffisantes.",
            "claims": [],
            "questions": [],
        })

    def unload(self) -> None:
        """Libérer la mémoire modèle."""
        self._model = None
        self._tokenizer = None
        self._onnx_session = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        logger.info("medgemma_runner.unloaded")
