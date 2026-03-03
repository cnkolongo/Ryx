"""RYX Imaging Service — DICOM storage + viewer + Pillar-0 trigger."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.imaging_import_agent import ImagingImportAgent
from .routes import health, imaging, viewer

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_bus.connect()
    agent = ImagingImportAgent(event_bus)
    task = asyncio.create_task(agent.run())
    yield
    agent.running = False
    task.cancel()
    await event_bus.disconnect()


app = FastAPI(
    title="RYX Imaging Service",
    description="DICOM management via Orthanc + viewer endpoints + Pillar-0 trigger",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(imaging.router, prefix="/v1", tags=["imaging"])
app.include_router(viewer.router, prefix="/v1", tags=["viewer"])
