import os
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import trace

from app.config import get_settings

_configured = False


def _otel_headers(value: str) -> dict[str, str] | None:
    if not value.strip():
        return None
    result: dict[str, str] = {}
    for item in value.split(","):
        key, separator, header_value = item.partition("=")
        if not separator or not key.strip():
            raise ValueError("OTEL_EXPORTER_OTLP_HEADERS must use key=value pairs")
        result[key.strip()] = header_value.strip()
    return result


def configure_observability() -> dict[str, object]:
    """Configure optional exporters without exposing credentials."""
    global _configured
    settings = get_settings()
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.otel_enabled and not _configured:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))
        if settings.otel_exporter_otlp_endpoint:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=_otel_headers(settings.otel_exporter_otlp_headers),
            )))
        trace.set_tracer_provider(provider)
        _configured = True
    return {
        "langsmith_enabled": bool(settings.langsmith_tracing and settings.langsmith_api_key),
        "otel_enabled": settings.otel_enabled,
    }


@contextmanager
def span(name: str, **attributes: object) -> Iterator[object]:
    with trace.get_tracer("enterprise-rd-agent").start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, str(value)[:500])
        yield current
