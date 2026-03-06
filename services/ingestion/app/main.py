"""RYX Ingestion Service — Réception et stockage de tous les documents."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus
from .routes import documents, health
from .storage import init_minio

logger = structlog.get_logger(__name__)
config = RyxConfig()

# Singleton EventBus — initialisé au démarrage, partagé par les routes
event_bus: EventBus | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_bus
    logger.info("ingestion_service.starting")
    await init_minio()
    event_bus = EventBus(redis_url=config.redis_url)
    await event_bus.connect()
    app.state.event_bus = event_bus
    yield
    logger.info("ingestion_service.stopping")
    if event_bus:
        await event_bus.disconnect()


app = FastAPI(
    title="RYX Ingestion Service",
    description="Upload PDF, images, DICOM — stockage MinIO + event ingestion.received",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(documents.router, prefix="/v1", tags=["documents"])
