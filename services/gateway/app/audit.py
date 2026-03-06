"""Audit Log — Traçabilité de toutes les actions (JAMAIS de PHI dans les logs)."""

from datetime import datetime
from uuid import uuid4

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None,
    user_id: str | None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Enregistre une action dans l'audit log.

    IMPORTANT :
    - Ne JAMAIS inclure de PHI dans les logs
    - Logguer les IDs, les actions, les timestamps — pas les contenus
    """
    audit_id = str(uuid4())
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    # Log structuré (indexable)
    logger.info(
        "audit",
        audit_id=audit_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        ip_address=ip_address,
    )

    # Persister en DB
    entry = AuditLog(
        audit_id=audit_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_=metadata or {},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    await db.commit()
