from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.api.auth import router as auth_router
from core.api.leads import router as leads_router
from core.db.session import Database
from core.models import affiliate, lead, offer  # noqa: F401
from core.services.worker_service import LeadWorker
from shared.logging import RequestContextMiddleware, setup_logging
from shared.redis import create_redis_client
from shared.settings import settings
from shared.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.service_name)
    app.state.database = Database(settings.database_url)
    app.state.redis = create_redis_client()

    configure_tracing(
        settings.service_name,
        app=app,
        engine=app.state.database.engine.sync_engine,
        redis_client=app.state.redis,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    )

    await app.state.redis.ping()
    await LeadWorker(app.state.redis, app.state.database.sessionmaker).ensure_group()

    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.database.dispose()


app = FastAPI(
    title="Core API",
    version="1.0.0",
    description="Core backend for JWT issuance, lead analytics, and background processing.",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(auth_router)
app.include_router(leads_router)


@app.get("/health", tags=["health"], summary="Core health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "core"}
