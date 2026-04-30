from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.db.session import Database
from core.models import affiliate, lead, offer  # noqa: F401
from landings.api.leads import router as leads_router
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
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.database.dispose()


app = FastAPI(
    title="Landings API",
    version="1.0.0",
    description="Lead intake service for landing pages.",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(leads_router)


@app.get("/health", tags=["health"], summary="Landings health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "landings"}
