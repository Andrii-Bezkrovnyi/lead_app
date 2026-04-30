from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

with suppress(ImportError):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
with suppress(ImportError):
    from opentelemetry.instrumentation.redis import RedisInstrumentor
with suppress(ImportError):
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

logger = logging.getLogger(__name__)

_instrumented = False


def configure_tracing(
        service_name: str,
        app: Any = None,
        engine: Any = None,
        redis_client: Any = None,
        otlp_endpoint: str = ""
) -> None:
    global _instrumented
    if _instrumented:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                f"OpenTelemetry: Tracing enabled for {service_name}, exporting to {otlp_endpoint}"
            )
        except Exception as e:
            logger.error(f"OpenTelemetry: Failed to initialize OTLP exporter: {e}")
    else:
        logger.info(
            f"OpenTelemetry: Tracing initialized in No-Op mode for {service_name} (no endpoint provided)"
        )

    trace.set_tracer_provider(provider)

    if app is not None:
        with suppress(Exception):
            FastAPIInstrumentor.instrument_app(app)

    if engine is not None:
        with suppress(Exception):
            SQLAlchemyInstrumentor().instrument(engine=engine)

    if redis_client is not None:
        with suppress(Exception):
            RedisInstrumentor().instrument()

    _instrumented = True
