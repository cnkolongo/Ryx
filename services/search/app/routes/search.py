"""Routes recherche — Patients + Knowledge Pack Q/A."""

import asyncio

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..meilisearch_client import search_patients, search_knowledge, get_client, INDEX_KNOWLEDGE

router = APIRouter()


class DocSearchRequest(BaseModel):
    query: str
    context_type: str = "knowledge"  # knowledge | patient | both
    patient_id: str | None = None
    top_k: int = 5
    language: str = "fr"


@router.get("/search/patients")
async def search_patients_endpoint(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Recherche full-text de patients (nom, prénom, MRN, téléphone).

    OFFLINE-COMPATIBLE : Meilisearch local.
    """
    try:
        result = await search_patients(q, limit=limit, offset=offset)
        return {
            "query": q,
            "hits": result.get("hits", []),
            "total": result.get("estimatedTotalHits", 0),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Index patient indisponible: {e}")


@router.post("/docsearch/query")
async def docsearch(body: DocSearchRequest):
    """
    Recherche documentaire sur le Knowledge Pack.

    OFFLINE-COMPATIBLE : Meilisearch local.
    Citations obligatoires dans la réponse.
    """
    sources = []

    if body.context_type in ("knowledge", "both"):
        try:
            result = await search_knowledge(
                body.query, limit=body.top_k, language=body.language
            )
            hits = result.get("hits", [])
            sources = [
                {
                    "doc_id": h.get("doc_id"),
                    "title": h.get("title", ""),
                    "excerpt": (h.get("content") or "")[:300],
                    "topic": h.get("topic", ""),
                    "source": h.get("source", ""),
                    "score": h.get("_rankingScore"),
                }
                for h in hits
            ]
        except Exception:
            sources = []  # Graceful degradation si Knowledge Pack pas indexé

    return {
        "query": body.query,
        "answer": (
            f"Résultats pour : {body.query}"
            if sources
            else "Aucune source disponible dans le Knowledge Pack."
        ),
        "sources": sources,
        "context_type_used": body.context_type,
        "offline": True,
        "knowledge_pack_version": "1.0",
    }


@router.get("/docsearch/topics")
async def list_topics():
    """Liste des topics disponibles dans le Knowledge Pack."""
    return {
        "topics": [
            "paludisme",
            "hypertension",
            "diabete",
            "tuberculose",
            "vih",
            "malnutrition",
            "cholera",
            "pneumonie",
            "drepanocytose",
            "grossesse",
        ]
    }


@router.get("/docsearch/status")
async def knowledge_pack_status():
    """Statut du Knowledge Pack (version, date, sources)."""
    from ryx_shared.config import RyxConfig
    config = RyxConfig()

    try:
        client = get_client()
        stats = await asyncio.to_thread(lambda: client.index(INDEX_KNOWLEDGE).get_stats())
        doc_count = stats.number_of_documents
    except Exception:
        doc_count = 0

    return {
        "version": config.knowledge_pack_version,
        "path": config.knowledge_pack_path,
        "offline_available": True,
        "indexed_documents": doc_count,
    }
