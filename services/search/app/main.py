"""RYX Search Service — Recherche patient + Knowledge Pack offline."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.indexer_agent import IndexerAgent
from .meilisearch_client import ensure_indexes
from .routes import health, search

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init Meilisearch indexes (idempotent)
    try:
        await ensure_indexes()
    except Exception as e:
        logger.warning("search.meilisearch_unavailable", error=str(e))
    await event_bus.connect()
    agent = IndexerAgent(event_bus)
    task = asyncio.create_task(agent.run())
    yield
    agent.running = False
    task.cancel()
    await event_bus.disconnect()


app = FastAPI(
    title="RYX Search Service",
    description="Index patient (Meilisearch) + Knowledge Pack Q/A offline",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(search.router, prefix="/v1", tags=["search"])
