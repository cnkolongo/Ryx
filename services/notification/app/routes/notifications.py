"""Routes notifications — Feed WebSocket + liste."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

router = APIRouter()
logger = structlog.get_logger(__name__)

# Registry des connexions WebSocket actives
active_connections: list[WebSocket] = []


@router.websocket("/notifications/feed")
async def websocket_feed(websocket: WebSocket):
    """Feed temps réel des notifications (WebSocket)."""
    # TODO: valider token JWT via query param ?token=...
    await websocket.accept()
    active_connections.append(websocket)
    logger.info("ws.connected", total=len(active_connections))
    try:
        while True:
            # Garder la connexion active (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("ws.disconnected", total=len(active_connections))


@router.get("/notifications")
async def list_notifications(page: int = 1, per_page: int = 20):
    """Liste des notifications de l'utilisateur courant."""
    # TODO: récupérer depuis DB
    return {"data": [], "pagination": {"page": page, "per_page": per_page, "total": 0}}


@router.patch("/notifications/{notification_id}/read")
async def mark_as_read(notification_id: str):
    """Marquer une notification comme lue."""
    return {"notification_id": notification_id, "read": True}
