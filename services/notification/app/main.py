"""RYX Notification Service — Dashboard WebSocket + WhatsApp (JAMAIS de PHI)."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.notification_agent import NotificationAgent
from .routes import health, notifications

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_bus.connect()
    agent = NotificationAgent(event_bus, config)
    task = asyncio.create_task(agent.run())
    yield
    agent.running = False
    task.cancel()
    await event_bus.disconnect()


app = FastAPI(
    title="RYX Notification Service",
    description="Alertes temps réel (WebSocket) + WhatsApp token-only. JAMAIS de PHI externe.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(notifications.router, prefix="/v1", tags=["notifications"])
