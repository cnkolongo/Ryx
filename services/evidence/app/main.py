"""RYX Evidence Service — EvidenceGuard + preuves cliquables."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.evidence_guard_agent import EvidenceGuardAgent
from .routes import health, evidence

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("evidence_service.starting")
    await event_bus.connect()

    agent = EvidenceGuardAgent(event_bus)
    task = asyncio.create_task(agent.run())

    yield

    agent.running = False
    task.cancel()
    await event_bus.disconnect()


app = FastAPI(
    title="RYX Evidence Service",
    description="EvidenceGuard policy engine — bloque tout claim non prouvé",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(evidence.router, prefix="/v1", tags=["evidence"])
