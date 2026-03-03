"""RYX Inference Service — Pillar-0 (vision) + MedGemma (raisonnement)."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.pillar0_agent import Pillar0Agent
from .agents.medgemma_agent import MedGemmaAgent
from .routes import health, reports

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("inference_service.starting", mode=config.ryx_mode)
    await event_bus.connect()

    # Démarrer les agents
    pillar0 = Pillar0Agent(event_bus, config)
    medgemma = MedGemmaAgent(event_bus, config)

    tasks = [
        asyncio.create_task(pillar0.run()),
        asyncio.create_task(medgemma.run()),
    ]

    yield

    pillar0.running = False
    medgemma.running = False
    for task in tasks:
        task.cancel()
    await event_bus.disconnect()
    logger.info("inference_service.stopping")


app = FastAPI(
    title="RYX Inference Service",
    description="Pillar-0 (CT/MRI vision) + MedGemma (raisonnement clinique)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(reports.router, prefix="/v1", tags=["reports"])
