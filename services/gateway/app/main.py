"""RYX Gateway — Point d'entrée unique (Auth, RBAC, Audit)."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from ryx_shared.config import RyxConfig

from .database import engine, Base
from .routes import auth, health, proxy

logger = structlog.get_logger(__name__)
config = RyxConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("gateway.starting", mode=config.ryx_mode, env=config.ryx_env)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("gateway.stopping")
    await engine.dispose()


app = FastAPI(
    title="RYX Gateway",
    description="Auth, RBAC, Audit et point d'entrée RYX",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
    redoc_url="/redoc" if not config.is_production else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not config.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Routes
app.include_router(health.router)
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(proxy.router, prefix="/v1", tags=["proxy"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("gateway.unhandled_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Une erreur interne est survenue",
            }
        },
    )
