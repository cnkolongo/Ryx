"""Routes recherche — Patients + Knowledge Pack Q/A."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class DocSearchRequest(BaseModel):
    query: str
    context_type: str = "knowledge"  # knowledge | patient | both
    patient_id: str | None = None
    top_k: int = 5
    language: str = "fr"


@router.post("/docsearch/query")
async def docsearch(body: DocSearchRequest):
    """
    Recherche documentaire + Q/A sur le Knowledge Pack.

    OFFLINE-COMPATIBLE : Meilisearch local + MedGemma edge.

    Règle : séparer clairement "connaissance générale" et "contexte patient".
    Citations obligatoires.
    """
    # TODO: implémenter avec Meilisearch + MedGemma
    return {
        "query": body.query,
        "answer": "Réponse en attente d'implémentation",
        "sources": [],
        "context_type_used": body.context_type,
        "offline": True,
        "knowledge_pack_version": "unknown",
    }


@router.get("/docsearch/topics")
async def list_topics():
    """Liste des topics disponibles dans le Knowledge Pack."""
    # TODO: lire depuis Meilisearch
    return {
        "topics": [
            "paludisme",
            "hypertension",
            "diabete",
            "tuberculose",
            "vih",
            "malnutrition",
        ]
    }


@router.get("/docsearch/status")
async def knowledge_pack_status():
    """Statut du Knowledge Pack (version, date, sources)."""
    import os
    from ryx_shared.config import RyxConfig
    config = RyxConfig()
    return {
        "version": config.knowledge_pack_version,
        "path": config.knowledge_pack_path,
        "offline_available": True,
    }
