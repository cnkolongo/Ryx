"""Audit Log — Traçabilité de toutes les actions (JAMAIS de PHI dans les logs)."""

from datetime import datetime
from uuid import UUID, uuid4

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None,
    user_id: UUID | None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Enregistre une action dans l'audit log.

    IMPORTANT :
    - Ne JAMAIS inclure de PHI dans les logs
    - Logguer les IDs, les actions, les timestamps — pas les contenus
    """
    audit_entry = {
        "audit_id": str(uuid4()),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_id": str(user_id) if user_id else None,
        "ip_address": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }

    # Log structuré (indexable)
    logger.info("audit", **audit_entry)

    # TODO: persister en DB (table audit_logs)
    # await db.execute(insert(AuditLog).values(**audit_entry))
    # await db.commit()
