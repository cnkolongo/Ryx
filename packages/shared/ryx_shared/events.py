"""RYX Events — Event Bus (Redis Streams) et topics."""

import json
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel, Field


# ─── Définition des topics ────────────────────────────────────────────────────

TOPICS = {
    # Pipeline ingestion
    "ingestion.received": "Document reçu et stocké, preprocessing à déclencher",
    "preprocess.completed": "OCR + extraction terminés",
    "imaging.imported": "DICOM importé dans Orthanc",

    # Pipeline IA
    "pillar0.requested": "Analyse Pillar-0 demandée",
    "pillar0.completed": "Analyse Pillar-0 terminée",
    "medgemma.requested": "Synthèse MedGemma demandée",
    "medgemma.completed": "Synthèse + claims MedGemma prêts (pending validation)",
    "prediction.requested": "Calcul prédictions demandé",
    "prediction.completed": "Prédictions calculées",

    # Pipeline evidence
    "evidence.validate.requested": "Validation EvidenceGuard demandée",
    "evidence.validate.completed": "Claims validés/bloqués",
    "evidence.blocked": "Un claim a été bloqué (preuve insuffisante)",

    # Post-processing
    "index.update.requested": "Mise à jour index patient/knowledge demandée",
    "index.update.completed": "Index mis à jour",
    "integration.sync.requested": "Sync DMI demandée",
    "integration.sync.completed": "Sync DMI terminée",
    "notify.requested": "Notification à envoyer",
    "notify.sent": "Notification envoyée",

    # Ops
    "ops.incident": "Incident infrastructure détecté",
}


# ─── Event model ──────────────────────────────────────────────────────────────

class RyxEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any]
    source_service: str
    correlation_id: str | None = None


# ─── Event Bus ────────────────────────────────────────────────────────────────

class EventBus:
    """
    Client Redis Streams pour publier/consommer des events RYX.

    Usage :
        bus = EventBus(redis_url="redis://localhost:6379")
        await bus.connect()

        # Publier
        await bus.publish("ingestion.received", {"doc_id": "..."}, source="ingestion")

        # Consommer (dans un agent)
        async for msg_id, event in bus.consume("preprocess.completed", "preprocess-group"):
            await process(event)
            await bus.ack("preprocess.completed", "preprocess-group", msg_id)
    """

    def __init__(self, redis_url: str, maxlen: int = 10000):
        self.redis_url = redis_url
        self.maxlen = maxlen
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("EventBus not connected. Call await bus.connect() first.")
        return self._redis

    async def publish(
        self,
        topic: str,
        payload: dict,
        source: str,
        correlation_id: str | None = None,
    ) -> str:
        """Publie un event dans un stream Redis. Retourne l'ID du message."""
        event = RyxEvent(
            topic=topic,
            payload=payload,
            source_service=source,
            correlation_id=correlation_id,
        )
        msg_id = await self.redis.xadd(
            topic,
            {"data": event.model_dump_json()},
            maxlen=self.maxlen,
            approximate=True,
        )
        return msg_id

    async def ensure_consumer_group(self, topic: str, group: str) -> None:
        """Crée le consumer group si inexistant."""
        try:
            await self.redis.xgroup_create(topic, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(
        self,
        topic: str,
        group: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, RyxEvent]]:
        """Consomme des messages d'un stream. Retourne liste (msg_id, event)."""
        messages = await self.redis.xreadgroup(
            groupname=group,
            consumername=consumer_name,
            streams={topic: ">"},
            count=count,
            block=block_ms,
        )
        results = []
        for _, msgs in (messages or []):
            for msg_id, data in msgs:
                event = RyxEvent.model_validate_json(data["data"])
                results.append((msg_id, event))
        return results

    async def ack(self, topic: str, group: str, msg_id: str) -> None:
        """Acknowledge un message traité."""
        await self.redis.xack(topic, group, msg_id)

    async def nack_dead_letter(self, topic: str, group: str, msg_id: str) -> None:
        """Déplace vers dead letter (claim le message sans ack)."""
        # En pratique : incrémenter retry_count, si > max → dead letter stream
        dl_topic = f"{topic}.dead-letter"
        raw = await self.redis.xrange(topic, min=msg_id, max=msg_id)
        if raw:
            await self.redis.xadd(dl_topic, raw[0][1])
        await self.redis.xack(topic, group, msg_id)
