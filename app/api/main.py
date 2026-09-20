from uuid import UUID
from fastapi import FastAPI, HTTPException

from app.config import Settings
from app.dlq.repository import create_repository
from app.domain.models import CallEvent
from app.observability import Metrics, cloudwatch_publisher, configure_logging
from app.providers.mock import MockPipelineProvider
from app.resilience import CircuitBreaker, ResilientPipeline
from app.services.processor import EventProcessor


def create_app(settings: Settings | None = None, processor: EventProcessor | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    if processor is None:
        if settings.provider_backend.lower() != "mock":
            raise RuntimeError("Open-weight backend requires injected STT, LLM, and TTS stage clients")
        provider = MockPipelineProvider(settings.downstream_url, settings.http_timeout_seconds)
        breaker = CircuitBreaker(settings.circuit_failure_threshold, settings.circuit_recovery_timeout_seconds, settings.circuit_half_open_probes)
        resilient = ResilientPipeline(provider, settings.max_attempts, settings.initial_backoff_seconds, settings.max_backoff_seconds, settings.jitter_ratio, breaker)
        publisher = cloudwatch_publisher(settings.cloudwatch_namespace, settings.service_name, settings.aws_region) if settings.publish_cloudwatch_metrics else None
        processor = EventProcessor(resilient, create_repository(settings), Metrics(publisher=publisher))
    app = FastAPI(title="Collections Inference Service", version="1.0.0")
    app.state.processor = processor

    @app.get("/health")
    async def health():
        return {"status": "ok", "circuit_state": app.state.processor.resilient.breaker.state.value}

    @app.get("/metrics")
    async def metrics():
        return app.state.processor.metrics.snapshot()

    @app.post("/events/process")
    async def process(event: CallEvent):
        return await app.state.processor.process(event)

    @app.get("/dlq")
    async def list_dlq(status: str | None = None):
        return app.state.processor.dlq.list(status)

    @app.post("/dlq/replay-pending")
    async def replay_pending():
        rows = app.state.processor.dlq.list()
        results = []
        for row in rows:
            if row["status"] in {"PENDING", "FAILED"}:
                result = await app.state.processor.replay(row["event_id"])
                if result:
                    results.append(result)
        return results

    @app.get("/dlq/{event_id}")
    async def inspect_dlq(event_id: UUID):
        row = app.state.processor.dlq.get(str(event_id))
        if not row:
            raise HTTPException(404, "event not found")
        return row

    @app.post("/dlq/{event_id}/replay")
    async def replay(event_id: UUID):
        result = await app.state.processor.replay(str(event_id))
        if result is None:
            raise HTTPException(404, "event not replayable")
        return result

    return app


app = create_app()
