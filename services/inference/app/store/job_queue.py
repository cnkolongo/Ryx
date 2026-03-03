"""
EdgeJobQueue — File d'attente SQLite pour le mode edge (offline).

Principe store & forward :
  1. Edge sans GPU → job sérialisé dans SQLite local
  2. Quand connectivité hub disponible → sync et exécution sur hub
  3. Idempotent : chaque job a un ID unique, statut tracé

Schema :
  edge_jobs(id, job_type, payload_json, status, created_at, updated_at, error)

Statuts :
  pending   → en attente de sync/exécution
  synced    → envoyé au hub (en attente de résultat)
  completed → traité avec succès
  failed    → échec après N tentatives
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Emplacement par défaut de la DB SQLite edge
DEFAULT_DB_PATH = "/data/edge/job_queue.db"


class EdgeJobQueue:
    """
    File d'attente de jobs persistante pour le mode edge.
    Thread-safe via asyncio.Lock + exécution SQLite dans thread pool.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Créer la table si elle n'existe pas encore."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edge_jobs (
                    id          TEXT PRIMARY KEY,
                    job_type    TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    attempts    INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    error       TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON edge_jobs (status)"
            )
            conn.commit()
        logger.debug("edge_job_queue.db_initialized", path=str(self.db_path))

    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        """
        Ajouter un job à la file d'attente.
        Retourne l'ID du job créé.
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._insert_job,
                job_id,
                job_type,
                payload,
                now,
            )

        logger.info(
            "edge_job_queue.enqueued",
            job_id=job_id,
            job_type=job_type,
        )
        return job_id

    def _insert_job(
        self, job_id: str, job_type: str, payload: dict, now: str
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO edge_jobs (id, job_type, payload, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (job_id, job_type, json.dumps(payload), now, now),
            )
            conn.commit()

    async def dequeue_pending(
        self, job_type: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Récupérer les jobs en attente pour synchronisation hub.
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, self._fetch_pending, job_type, limit
        )
        return rows

    def _fetch_pending(
        self, job_type: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if job_type:
                cursor = conn.execute(
                    """
                    SELECT * FROM edge_jobs
                    WHERE status = 'pending' AND job_type = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (job_type, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM edge_jobs
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "job_type": row["job_type"],
                "payload": json.loads(row["payload"]),
                "status": row["status"],
                "attempts": row["attempts"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def mark_synced(self, job_id: str) -> None:
        """Marquer le job comme envoyé au hub."""
        await self._update_status(job_id, "synced")

    async def mark_completed(self, job_id: str) -> None:
        """Marquer le job comme traité avec succès."""
        await self._update_status(job_id, "completed")
        logger.info("edge_job_queue.completed", job_id=job_id)

    async def mark_failed(self, job_id: str, error: str) -> None:
        """Marquer le job comme échoué avec le message d'erreur."""
        now = datetime.now(timezone.utc).isoformat()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._set_failed, job_id, error, now
        )
        logger.error("edge_job_queue.failed", job_id=job_id, error=error[:200])

    def _set_failed(self, job_id: str, error: str, now: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE edge_jobs
                SET status = 'failed', error = ?, updated_at = ?,
                    attempts = attempts + 1
                WHERE id = ?
                """,
                (error[:500], now, job_id),
            )
            conn.commit()

    async def _update_status(self, job_id: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._set_status, job_id, status, now
        )

    def _set_status(self, job_id: str, status: str, now: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE edge_jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, job_id),
            )
            conn.commit()

    async def stats(self) -> dict[str, int]:
        """Statistiques de la file (pour health check / monitoring)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_stats)

    def _fetch_stats(self) -> dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM edge_jobs GROUP BY status"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
