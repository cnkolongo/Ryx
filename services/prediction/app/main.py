"""RYX Prediction Service — Prédictions longitudinales (plugin-based)."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig
from ryx_shared.events import EventBus

from .agents.prediction_agent import PredictionAgent
from .routes import health, predictions

logger = structlog.get_logger(__name__)
config = RyxConfig()
event_bus = EventBus(config.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_bus.connect()
    agent = PredictionAgent(event_bus)
    task = asyncio.create_task(agent.run())
    yield
    agent.running = False
    task.cancel()
    await event_bus.disconnect()


app = FastAPI(
    title="RYX Prediction Service",
    description="Scores longitudinaux 30d/6m/1y/2y — architecture plugin",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(health.router)
app.include_router(predictions.router, prefix="/v1", tags=["predictions"])
