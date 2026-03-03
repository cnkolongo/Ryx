"""Reverse proxy vers les services internes."""

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from ryx_shared.config import RyxConfig

from ..auth import TokenPayload, get_current_user
from ..audit import log_action

logger = structlog.get_logger(__name__)
config = RyxConfig()
router = APIRouter()

# Mapping route prefix → service URL
SERVICE_ROUTES = {
    "/patients": config.patient_service_url,
    "/encounters": config.patient_service_url,
    "/documents": config.ingestion_service_url,
    "/imaging": config.imaging_service_url,
    "/viewer": config.imaging_service_url,
    "/reports": config.inference_service_url,
    "/predictions": config.prediction_service_url,
    "/docsearch": config.search_service_url,
    "/integration": config.integration_service_url,
    "/notifications": config.notification_service_url,
}


async def get_service_url(path: str) -> str | None:
    for prefix, url in SERVICE_ROUTES.items():
        if path.startswith(prefix):
            return url
    return None


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(
    request: Request,
    path: str,
    user: Annotated[TokenPayload, Depends(get_current_user)],
):
    """Proxy authentifié vers les services internes."""
    full_path = f"/{path}"
    service_url = await get_service_url(full_path)

    if not service_url:
        raise HTTPException(status_code=404, detail=f"Route non trouvée : {full_path}")

    target_url = f"{service_url}/v1{full_path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    # Audit log
    await log_action(
        db=None,  # TODO: passer session DB
        action=f"{request.method}:{full_path}",
        resource_type=full_path.split("/")[1] if "/" in full_path else "unknown",
        resource_id=None,
        user_id=user.user_id,
        request=request,
    )

    # Forward la requête avec headers auth
    headers = dict(request.headers)
    headers["X-User-Id"] = str(user.user_id)
    headers["X-User-Role"] = user.role.value
    # Retirer headers qui ne doivent pas être forwardés
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            body = await request.body()
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )
    except httpx.ConnectError:
        logger.error("proxy.service_unreachable", target=target_url)
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")
