import asyncio
import pytest
from app.dlq.repository import DLQRepository
from app.domain.models import CallEvent, PipelineResult
from app.observability import Metrics
from app.resilience import CircuitBreaker, ResilientPipeline
from app.services.processor import EventProcessor
from app.providers.mock import DownstreamError
from uuid import uuid4


def event(): return CallEvent(event_id=uuid4(), campaign_id="C", borrower_bucket="0-30 DPD", timestamp="2026-09-01T00:00:00Z", outcome="connected")


class AlwaysDown:
    async def process(self, _): raise DownstreamError("down", transient=True)


@pytest.mark.asyncio
async def test_persistent_failure_enters_dlq(tmp_path):
    repository = DLQRepository(str(tmp_path / "x.sqlite3"))
    resilient = ResilientPipeline(AlwaysDown(), 2, 0, 1, 0, CircuitBreaker(5, 10), sleep_fn=lambda _: None)
    processor = EventProcessor(resilient, repository, Metrics())
    result = await processor.process(event())
    assert not result.success and repository.list()[0]["retry_count"] == 1


@pytest.mark.asyncio
async def test_duplicate_success_is_idempotent(tmp_path):
    class Good:
        def __init__(self): self.calls = 0
        async def process(self, _):
            self.calls += 1
            return PipelineResult(status="ok", transcript="x", response_audio_ref="x", latency_ms=1)
    provider = Good(); repository = DLQRepository(str(tmp_path / "x.sqlite3"))
    processor = EventProcessor(ResilientPipeline(provider, 1, 0, 1, 0, CircuitBreaker(2, 10)), repository, Metrics())
    item = event(); await processor.process(item); await processor.process(item)
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_success_is_idempotent(tmp_path):
    class SlowGood:
        def __init__(self): self.calls = 0
        async def process(self, _):
            self.calls += 1
            await asyncio.sleep(0.01)
            return PipelineResult(status="ok", transcript="x", response_audio_ref="x", latency_ms=1)
    provider = SlowGood(); repository = DLQRepository(str(tmp_path / "x.sqlite3"))
    processor = EventProcessor(ResilientPipeline(provider, 1, 0, 1, 0, CircuitBreaker(2, 10)), repository, Metrics())
    item = event()
    results = await asyncio.gather(processor.process(item), processor.process(item))
    assert provider.calls == 1 and all(result.success for result in results)
