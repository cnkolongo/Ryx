"""
Pillar-0 Runner — Intégration officielle YalaLab/Pillar-0

Modèles HuggingFace :
  - YalaLab/Pillar0-ChestCT     → CT thorax (pneumonie, nodules, épanchement...)
  - YalaLab/Pillar0-HeadCT      → CT tête (hémorragie, AVC, hydrocéphalie...)
  - YalaLab/Pillar0-AbdomenCT   → CT abdomen-pelvis (appendicite, tumeurs...)
  - YalaLab/Pillar0-BreastMRI   → IRM sein (masse, asymétrie...)

Architecture : Atlas Vision Encoder + Qwen3-Embedding-8B (text encoder)
Preprocessing : RAVE (Radiology Vision Engine) — DICOM → tenseur ML

Références :
  - Paper   : https://arxiv.org/abs/2511.17803
  - Models  : https://huggingface.co/collections/YalaLab/pillar-0
  - RAVE    : https://github.com/YalaLab/rave
  - Finetune: https://github.com/YalaLab/pillar-finetune
"""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import torch

logger = structlog.get_logger(__name__)


# ─── Modalités supportées ─────────────────────────────────────────────────────

class Pillar0Modality(str, Enum):
    """
    Modèle Pillar-0 par modalité radiologique.
    Choisir le modèle selon la modalité DICOM de l'étude.
    """
    CHEST_CT    = "YalaLab/Pillar0-ChestCT"
    HEAD_CT     = "YalaLab/Pillar0-HeadCT"
    ABDOMEN_CT  = "YalaLab/Pillar0-AbdomenCT"
    BREAST_MRI  = "YalaLab/Pillar0-BreastMRI"


# Mapping DICOM body part → modèle Pillar-0
# Source : DICOM tag (0018,0015) BodyPartExamined
BODY_PART_TO_MODEL: dict[str, Pillar0Modality] = {
    # CT Thorax
    "CHEST": Pillar0Modality.CHEST_CT,
    "LUNG": Pillar0Modality.CHEST_CT,
    "THORAX": Pillar0Modality.CHEST_CT,
    # CT Tête
    "HEAD": Pillar0Modality.HEAD_CT,
    "BRAIN": Pillar0Modality.HEAD_CT,
    "SKULL": Pillar0Modality.HEAD_CT,
    "NECK": Pillar0Modality.HEAD_CT,
    # CT Abdomen
    "ABDOMEN": Pillar0Modality.ABDOMEN_CT,
    "PELVIS": Pillar0Modality.ABDOMEN_CT,
    "ABDOMINOPELVIS": Pillar0Modality.ABDOMEN_CT,
    "LIVER": Pillar0Modality.ABDOMEN_CT,
    # IRM Sein
    "BREAST": Pillar0Modality.BREAST_MRI,
}

# Modalities DICOM valides pour Pillar-0
SUPPORTED_DICOM_MODALITIES = {"CT", "MR"}


# ─── Output ───────────────────────────────────────────────────────────────────

@dataclass
class Pillar0Finding:
    """
    Un finding radiologique détecté par Pillar-0.
    Correspond à une des 366 questions cliniques de RATE.
    """
    label: str          # ex: "pleural_effusion", "intracranial_hemorrhage"
    score: float        # probabilité 0.0–1.0
    positive: bool      # score > seuil (0.5 par défaut)
    category: str       # ex: "thoracic", "neurological"
    # Localisation volumétrique (si disponible via Pillar-Finetune)
    roi_slice: int | None = None       # slice index dans la série
    roi_bbox: tuple | None = None      # (x1, y1, x2, y2) normalisé


@dataclass
class Pillar0Result:
    study_id: str
    modality: Pillar0Modality
    model_version: str
    findings: list[Pillar0Finding]
    # Findings cliniquement significatifs (score > seuil)
    positive_findings: list[Pillar0Finding] = field(default_factory=list)
    # Slice la plus représentative par finding (pour EvidenceRef DICOM)
    key_slices: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.positive_findings = [f for f in self.findings if f.positive]


# ─── Runner ───────────────────────────────────────────────────────────────────

class Pillar0Runner:
    """
    Runner Pillar-0 — charge le modèle depuis HuggingFace et analyse des volumes DICOM.

    Usage :
        runner = Pillar0Runner(cache_dir="/models/pillar-0")
        await runner.load(Pillar0Modality.CHEST_CT)
        result = await runner.analyze(dicom_series_paths, study_id="uuid")

    Le runner maintient un cache de modèles chargés pour éviter les rechargements.
    """

    def __init__(
        self,
        cache_dir: str = "/models/pillar-0",
        device: str | None = None,
        confidence_threshold: float = 0.5,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.confidence_threshold = confidence_threshold
        self._models: dict[Pillar0Modality, Any] = {}
        self._processors: dict[Pillar0Modality, Any] = {}

        # Auto-détection GPU
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(
            "pillar0_runner.initialized",
            device=self.device,
            cache_dir=str(self.cache_dir),
        )

    async def load(self, modality: Pillar0Modality) -> None:
        """
        Charger le modèle Pillar-0 pour une modalité donnée.
        Téléchargement automatique depuis HuggingFace si absent du cache.
        """
        if modality in self._models:
            return  # déjà chargé

        logger.info("pillar0_runner.loading_model", modality=modality.value)

        # Charger en thread pool (opération bloquante)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(self._load_sync, modality),
        )

        logger.info("pillar0_runner.model_loaded", modality=modality.value, device=self.device)

    def _load_sync(self, modality: Pillar0Modality) -> None:
        """Chargement synchrone du modèle (à appeler dans un thread pool)."""
        from transformers import AutoModel, AutoProcessor

        model = AutoModel.from_pretrained(
            modality.value,
            cache_dir=str(self.cache_dir),
            trust_remote_code=True,  # Pillar-0 utilise une architecture custom (Atlas)
        )
        model = model.to(self.device)
        model.eval()

        processor = AutoProcessor.from_pretrained(
            modality.value,
            cache_dir=str(self.cache_dir),
            trust_remote_code=True,
        )

        self._models[modality] = model
        self._processors[modality] = processor

    async def analyze(
        self,
        dicom_paths: list[str],
        study_id: str,
        body_part: str | None = None,
        modality_override: Pillar0Modality | None = None,
    ) -> Pillar0Result:
        """
        Analyser une série DICOM avec Pillar-0.

        Args:
            dicom_paths   : liste des fichiers .dcm de la série (ordonnés)
            study_id      : ID de l'étude (pour logging + résultat)
            body_part     : BodyPartExamined DICOM (ex: "CHEST", "HEAD")
            modality_override : forcer une modalité (ignore body_part)

        Returns:
            Pillar0Result avec findings et positive_findings
        """
        # Sélectionner le modèle selon la modalité
        pillar_modality = modality_override or self._detect_modality(body_part, dicom_paths)
        await self.load(pillar_modality)

        logger.info(
            "pillar0_runner.analyzing",
            study_id=study_id,
            modality=pillar_modality.value,
            slices=len(dicom_paths),
        )

        # Préprocessing DICOM → tenseur (via RAVE ou pydicom)
        volume = await self._preprocess_dicom(dicom_paths, pillar_modality)

        # Inférence (dans thread pool — opération GPU bloquante)
        loop = asyncio.get_event_loop()
        raw_scores = await loop.run_in_executor(
            None,
            functools.partial(self._infer_sync, volume, pillar_modality),
        )

        # Post-processing → findings
        findings = self._postprocess(raw_scores, pillar_modality)

        result = Pillar0Result(
            study_id=study_id,
            modality=pillar_modality,
            model_version=pillar_modality.value,
            findings=findings,
        )

        logger.info(
            "pillar0_runner.analysis_done",
            study_id=study_id,
            total_findings=len(findings),
            positive_findings=len(result.positive_findings),
            top_findings=[f.label for f in result.positive_findings[:5]],
        )

        return result

    def _detect_modality(
        self, body_part: str | None, dicom_paths: list[str]
    ) -> Pillar0Modality:
        """
        Détecter la modalité depuis BodyPartExamined ou les tags DICOM.
        Fallback : ChestCT (le plus courant en contexte terrain RDC).
        """
        if body_part:
            normalized = body_part.upper().replace(" ", "").replace("-", "")
            if normalized in BODY_PART_TO_MODEL:
                return BODY_PART_TO_MODEL[normalized]

        # Lire depuis le premier fichier DICOM
        if dicom_paths:
            try:
                import pydicom
                ds = pydicom.dcmread(dicom_paths[0], stop_before_pixels=True)
                bp = getattr(ds, "BodyPartExamined", "").upper().strip()
                if bp in BODY_PART_TO_MODEL:
                    return BODY_PART_TO_MODEL[bp]
            except Exception:
                pass

        logger.warning(
            "pillar0_runner.modality_unknown",
            body_part=body_part,
            fallback="ChestCT",
        )
        return Pillar0Modality.CHEST_CT  # fallback

    async def _preprocess_dicom(
        self, dicom_paths: list[str], modality: Pillar0Modality
    ) -> torch.Tensor:
        """
        Convertir les fichiers DICOM en tenseur ML via RAVE.

        RAVE applique :
        1. Resampling isotropique
        2. Multi-windowing (windows HU selon modalité)
        3. Normalisation spatiale à dimensions fixes
        → Tenseur GPU-ready

        Si RAVE n'est pas disponible → fallback pydicom+numpy.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(self._preprocess_sync, dicom_paths, modality),
        )

    def _preprocess_sync(
        self, dicom_paths: list[str], modality: Pillar0Modality
    ) -> torch.Tensor:
        """Préprocessing synchrone — RAVE en priorité, pydicom en fallback."""
        try:
            return self._preprocess_with_rave(dicom_paths, modality)
        except ImportError:
            logger.warning("pillar0_runner.rave_not_available", fallback="pydicom")
            return self._preprocess_with_pydicom(dicom_paths)

    def _preprocess_with_rave(
        self, dicom_paths: list[str], modality: Pillar0Modality
    ) -> torch.Tensor:
        """
        Preprocessing via RAVE (recommandé — même pipeline que le training Pillar-0).
        https://github.com/YalaLab/rave
        """
        from rave import DicomProcessor, WindowingConfig

        # Configuration multi-windowing selon la modalité
        # (réplique le preprocessing d'entraînement Pillar-0)
        window_configs = _get_windowing_config(modality)

        processor = DicomProcessor(
            windowing=window_configs,
            target_spacing=(1.5, 1.5, 1.5),  # mm isotrope
            target_shape=(224, 224, 128),     # D×H×W
        )
        volume = processor.process(dicom_paths)  # → np.ndarray
        tensor = torch.from_numpy(volume).float().to(self.device)
        return tensor.unsqueeze(0)  # batch dim

    def _preprocess_with_pydicom(self, dicom_paths: list[str]) -> torch.Tensor:
        """
        Fallback preprocessing minimal avec pydicom + numpy.
        Moins précis que RAVE mais fonctionnel.
        """
        import pydicom

        slices = []
        for path in sorted(dicom_paths):
            ds = pydicom.dcmread(path)
            pixel_array = ds.pixel_array.astype(np.float32)
            # Appliquer rescale slope/intercept (Hounsfield units pour CT)
            slope = float(getattr(ds, "RescaleSlope", 1.0))
            intercept = float(getattr(ds, "RescaleIntercept", 0.0))
            pixel_array = pixel_array * slope + intercept
            slices.append(pixel_array)

        if not slices:
            raise ValueError("Aucun slice DICOM chargé")

        volume = np.stack(slices, axis=0)  # (D, H, W)
        # Windowing CT soft tissue : [-150, 250] HU → [0, 1]
        volume = np.clip(volume, -150, 250)
        volume = (volume + 150) / 400.0
        tensor = torch.from_numpy(volume).float().unsqueeze(0).unsqueeze(0)
        return tensor.to(self.device)

    def _infer_sync(self, volume: torch.Tensor, modality: Pillar0Modality) -> dict:
        """Inférence GPU synchrone."""
        model = self._models[modality]
        with torch.no_grad():
            outputs = model(pixel_values=volume)
            # Pillar-0 retourne des logits pour chaque classe (RATE labels)
            logits = outputs.logits if hasattr(outputs, "logits") else outputs[0]
            scores = torch.sigmoid(logits).cpu().numpy()
        return {"scores": scores, "modality": modality}

    def _postprocess(
        self, raw_output: dict, modality: Pillar0Modality
    ) -> list[Pillar0Finding]:
        """
        Convertir les scores bruts Pillar-0 en Pillar0Finding.
        Les labels correspondent aux 366 findings RATE.
        """
        scores = raw_output["scores"].flatten()
        label_list = _get_rate_labels(modality)

        findings = []
        for i, (label, score) in enumerate(zip(label_list, scores)):
            findings.append(Pillar0Finding(
                label=label,
                score=float(score),
                positive=float(score) >= self.confidence_threshold,
                category=_get_category(label),
            ))

        # Trier par score décroissant
        return sorted(findings, key=lambda f: f.score, reverse=True)

    def unload(self, modality: Pillar0Modality | None = None) -> None:
        """Libérer la mémoire GPU pour un ou tous les modèles."""
        targets = [modality] if modality else list(self._models.keys())
        for m in targets:
            if m in self._models:
                del self._models[m]
                del self._processors[m]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("pillar0_runner.models_unloaded", targets=[m.value for m in targets])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_windowing_config(modality: Pillar0Modality) -> list[dict]:
    """
    Multi-windowing HU par modalité — réplique le preprocessing Pillar-0.
    Source : Section 2.3 du paper arXiv:2511.17803
    """
    if modality == Pillar0Modality.CHEST_CT:
        return [
            {"center": -600, "width": 1500, "name": "lung"},
            {"center": 40,   "width": 400,  "name": "soft_tissue"},
            {"center": 700,  "width": 1000, "name": "bone"},
        ]
    elif modality == Pillar0Modality.HEAD_CT:
        return [
            {"center": 35,  "width": 80,   "name": "brain"},
            {"center": 75,  "width": 200,  "name": "subdural"},
            {"center": 600, "width": 2800, "name": "bone"},
        ]
    elif modality == Pillar0Modality.ABDOMEN_CT:
        return [
            {"center": 60,  "width": 400,  "name": "soft_tissue"},
            {"center": 300, "width": 1500, "name": "liver"},
            {"center": 700, "width": 1000, "name": "bone"},
        ]
    elif modality == Pillar0Modality.BREAST_MRI:
        # MRI : pas de HU, normalisation par percentile
        return [{"percentile_low": 2, "percentile_high": 98, "name": "standard"}]
    return [{"center": 40, "width": 400, "name": "soft_tissue"}]


def _get_rate_labels(modality: Pillar0Modality) -> list[str]:
    """
    Labels RATE (366 findings) pour chaque modalité.
    Sous-ensemble pertinent par modalité (cf. paper + RATE repo).
    Source : https://github.com/YalaLab/rate
    """
    if modality == Pillar0Modality.CHEST_CT:
        return [
            "pleural_effusion", "pneumothorax", "consolidation", "atelectasis",
            "ground_glass_opacity", "pulmonary_nodule", "emphysema",
            "pericardial_effusion", "cardiomegaly", "pneumonia",
            "pulmonary_edema", "lung_mass", "lymphadenopathy",
            "aortic_aneurysm", "pulmonary_embolism",
        ]
    elif modality == Pillar0Modality.HEAD_CT:
        return [
            "intracranial_hemorrhage", "subdural_hematoma", "epidural_hematoma",
            "subarachnoid_hemorrhage", "intraventricular_hemorrhage",
            "cerebral_edema", "midline_shift", "hydrocephalus",
            "ischemic_stroke", "skull_fracture", "mass_effect",
            "cerebral_contusion", "hyperdense_lesion",
        ]
    elif modality == Pillar0Modality.ABDOMEN_CT:
        return [
            "liver_lesion", "gallstones", "cholecystitis", "appendicitis",
            "bowel_obstruction", "free_fluid", "free_air", "pancreatitis",
            "renal_calculi", "hydronephrosis", "adrenal_lesion",
            "aortic_aneurysm", "lymphadenopathy", "splenomegaly",
        ]
    elif modality == Pillar0Modality.BREAST_MRI:
        return [
            "mass", "non_mass_enhancement", "asymmetry",
            "lymph_node_enlargement", "skin_thickening",
            "nipple_retraction", "suspicious_lesion",
        ]
    return []


def _get_category(label: str) -> str:
    """Catégorie clinique d'un label RATE."""
    categories = {
        "pleural": "thoracic", "pneumo": "thoracic", "pulmonary": "thoracic",
        "lung": "thoracic", "cardiac": "cardiovascular", "aortic": "cardiovascular",
        "intracranial": "neurological", "cerebral": "neurological",
        "subdural": "neurological", "skull": "neurological",
        "liver": "abdominal", "gallstone": "abdominal", "bowel": "abdominal",
        "renal": "abdominal", "pancreatic": "abdominal",
        "mass": "oncological", "lesion": "oncological",
    }
    label_lower = label.lower()
    for key, cat in categories.items():
        if key in label_lower:
            return cat
    return "general"
