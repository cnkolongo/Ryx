"""Extractor — Extraction structurée (labs, constantes) depuis blocs OCR."""

import re
import structlog
from ryx_shared.models import OcrBlock, LabResult, ReferenceRange

logger = structlog.get_logger(__name__)

# Patterns de reconnaissance de valeurs de labo (FR + EN)
LAB_PATTERNS = [
    # Créatinine: 1.2 mg/dL ou Créatinine : 1.2 mg/dl
    r"(?:cr[eé]atinine|creatinine)\s*[:\-]?\s*(\d+\.?\d*)\s*(mg/d[lL]|µmol/L|umol/L)",
    # Hémoglobine: 11.5 g/dL
    r"(?:h[eé]moglobine|hemoglobin|hgb|hb)\s*[:\-]?\s*(\d+\.?\d*)\s*(g/d[lL]|g/L)",
    # CRP
    r"(?:crp|c-reactive protein|prot[eé]ine c r[eé]active)\s*[:\-]?\s*(\d+\.?\d*)\s*(mg/L|mg/d[lL])",
    # Glycémie / Glucose
    r"(?:glyc[eé]mie|glucose|gly)\s*[:\-]?\s*(\d+\.?\d*)\s*(mmol/L|mg/d[lL]|g/L)",
    # SPO2
    r"(?:spo2|saturation|sat\.?\s*o2)\s*[:\-]?\s*(\d+\.?\d*)\s*(%|pourcent)",
]


async def extract_labs(ocr_blocks: list[OcrBlock]) -> list[dict]:
    """
    Extraire les résultats de laboratoire depuis les blocs OCR.
    Retourne liste de dicts (à convertir en LabResult).
    """
    full_text = " ".join(b.text for b in ocr_blocks)
    extracted = []

    for pattern in LAB_PATTERNS:
        matches = re.finditer(pattern, full_text, re.IGNORECASE)
        for match in matches:
            extracted.append({
                "test": _get_test_name(pattern),
                "value": float(match.group(1)),
                "unit": match.group(2),
                "raw_text": match.group(0),
            })

    return extracted


async def extract_vitals(ocr_blocks: list[OcrBlock]) -> list[dict]:
    """Extraire les constantes vitales."""
    full_text = " ".join(b.text for b in ocr_blocks)
    vitals = []

    # TA: 120/80 mmHg
    ta_match = re.search(r"(?:ta|tension|pa|bp)\s*[:\-]?\s*(\d+)/(\d+)\s*(?:mmhg)?", full_text, re.I)
    if ta_match:
        vitals.append({"test": "ta_systolique", "value": float(ta_match.group(1)), "unit": "mmHg"})
        vitals.append({"test": "ta_diastolique", "value": float(ta_match.group(2)), "unit": "mmHg"})

    # FC: 80 bpm
    fc_match = re.search(r"(?:fc|freq(?:uence)? cardiaque|hr|pouls)\s*[:\-]?\s*(\d+)\s*(?:bpm)?", full_text, re.I)
    if fc_match:
        vitals.append({"test": "frequence_cardiaque", "value": float(fc_match.group(1)), "unit": "bpm"})

    # Température: 38.5 °C
    temp_match = re.search(r"(?:t[eé]mp[eé]rature|temp|t°|fièvre)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:°c|c)?", full_text, re.I)
    if temp_match:
        vitals.append({"test": "temperature", "value": float(temp_match.group(1)), "unit": "°C"})

    return vitals


def _get_test_name(pattern: str) -> str:
    """Extraire le nom du test depuis le pattern regex."""
    # Mapping simple pattern → nom normalisé
    mappings = {
        "cr[eé]atinine": "creatinine",
        "h[eé]moglobine": "hemoglobine",
        "crp": "crp",
        "glyc[eé]mie": "glycemie",
        "spo2": "spo2",
    }
    for key, name in mappings.items():
        if key.lower() in pattern.lower():
            return name
    return "unknown"
