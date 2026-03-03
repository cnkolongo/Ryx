"""RYX Preprocess Service — OCR, nettoyage, extraction données structurées."""

import structlog
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.preprocess_agent import PreprocessAgent
from .routes import health

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("preprocess_service.starting")
    await event_bus.connect()

    # Démarrer l'agent en background
    agent = PreprocessAgent(event_bus)
    task = asyncio.create_task(agent.run())

    yield

    agent.running = False
    task.cancel()
    await event_bus.disconnect()
    logger.info("preprocess_service.stopping")


app = FastAPI(
    title="RYX Preprocess Service",
    description="OCR + nettoyage + extraction structurée",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
