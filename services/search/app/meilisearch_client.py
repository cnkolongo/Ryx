"""Meilisearch client — index patients + Knowledge Pack."""

import asyncio
from typing import Any

import meilisearch
import structlog

from ryx_shared.config import RyxConfig

logger = structlog.get_logger(__name__)
config = RyxConfig()

# Index names
INDEX_PATIENTS = "patients"
INDEX_KNOWLEDGE = "knowledge"

# Meilisearch client (sync — wrapped with asyncio.to_thread)
_client: meilisearch.Client | None = None


def get_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(
            config.meilisearch_url,
            config.meilisearch_key or None,
        )
    return _client


async def ensure_indexes() -> None:
    """Create indexes with proper settings if they don't exist."""
    client = get_client()

    def _setup():
        # Patients index
        try:
            client.create_index(INDEX_PATIENTS, {"primaryKey": "patient_id"})
        except Exception:
            pass  # Already exists
        idx = client.index(INDEX_PATIENTS)
        idx.update_searchable_attributes([
            "last_name", "first_name", "mrn", "phone",
            "encounter_diagnoses", "claim_texts",
        ])
        idx.update_filterable_attributes(["gender", "patient_id"])
        idx.update_sortable_attributes(["last_seen_at"])

        # Knowledge Pack index
        try:
            client.create_index(INDEX_KNOWLEDGE, {"primaryKey": "doc_id"})
        except Exception:
            pass
        kidx = client.index(INDEX_KNOWLEDGE)
        kidx.update_searchable_attributes([
            "title", "content", "tags", "keywords",
        ])
        kidx.update_filterable_attributes(["topic", "language", "source"])

    await asyncio.to_thread(_setup)
    logger.info("meilisearch.indexes_ready")


async def index_patient(patient_doc: dict[str, Any]) -> None:
    """Upsert a patient document into the patients index."""
    client = get_client()

    def _index():
        client.index(INDEX_PATIENTS).add_documents([patient_doc])

    await asyncio.to_thread(_index)


async def search_patients(
    query: str,
    limit: int = 20,
    offset: int = 0,
    filter_expr: str | None = None,
) -> dict[str, Any]:
    """Full-text search on patients index."""
    client = get_client()

    def _search():
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if filter_expr:
            params["filter"] = filter_expr
        return client.index(INDEX_PATIENTS).search(query, params)

    result = await asyncio.to_thread(_search)
    return result


async def search_knowledge(
    query: str,
    limit: int = 10,
    language: str = "fr",
    topic: str | None = None,
) -> dict[str, Any]:
    """Full-text search on Knowledge Pack index."""
    client = get_client()

    def _search():
        filters = [f"language = {language}"]
        if topic:
            filters.append(f"topic = {topic}")
        return client.index(INDEX_KNOWLEDGE).search(query, {
            "limit": limit,
            "filter": " AND ".join(filters),
            "attributesToHighlight": ["title", "content"],
        })

    result = await asyncio.to_thread(_search)
    return result


async def index_knowledge_doc(doc: dict[str, Any]) -> None:
    """Upsert a Knowledge Pack document."""
    client = get_client()

    def _index():
        client.index(INDEX_KNOWLEDGE).add_documents([doc])

    await asyncio.to_thread(_index)
