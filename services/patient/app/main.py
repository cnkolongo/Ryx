"""RYX Patient Service — Mini-DMI (patients, encounters, timeline)."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig

from .routes import patients, encounters, health

logger = structlog.get_logger(__name__)
config = RyxConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("patient_service.starting", mode=config.ryx_mode)
    yield
    logger.info("patient_service.stopping")


app = FastAPI(
    title="RYX Patient Service",
    description="Mini-DMI : patients, encounters, timeline",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(health.router)
app.include_router(patients.router, prefix="/v1", tags=["patients"])
app.include_router(encounters.router, prefix="/v1", tags=["encounters"])
