# ADR-002 — Python + FastAPI pour les services backend

**Date** : 2026-03-03
**Statut** : Accepté

## Contexte
RYX est un système IA clinique. Les services backend doivent :
- Intégrer des modèles ML (Pillar-0, MedGemma, OCR)
- Être async et performants
- Avoir une bonne DX pour vibecoding

## Décision
**Python 3.12 + FastAPI + Pydantic v2** pour tous les services backend.
**uv** comme gestionnaire de packages (rapide, moderne).

## Raisons
1. **Écosystème ML unifié** : PyTorch, HuggingFace, ONNX Runtime, OpenCV, EasyOCR — tout en Python
2. **FastAPI** : async natif, validation Pydantic auto, OpenAPI généré, excellent pour vibecoding
3. **Pydantic v2** : validation performante, type safety, sérialisation JSON native
4. **SQLAlchemy 2.0 async** : ORM robuste, migrations via Alembic
5. **uv** : 10-100x plus rapide que pip, lockfile, gestion deps propre

## Alternatives considérées
- **Go** : performance excellente, mais pas d'écosystème ML — rejeté
- **Node.js** : bon pour gateway/notification, mauvais pour ML — considéré pour gateway uniquement
- **Rust** : trop de friction pour vibecoding — rejeté
- **Mix Python + Go** : complexité inutile pour MVP — rejeté

## Conséquences
- `+` Un seul langage pour tous les devs (réduction de friction)
- `+` Modèles ML directement dans les services (pas de bridge)
- `+` OpenAPI auto-générée par FastAPI
- `-` Python moins performant que Go/Rust pour du CPU pur
- Mitigation : ONNX Runtime pour ML optimisé, Uvicorn async pour I/O
