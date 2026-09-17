import pytest
from app.domain.models import CallEvent, PipelineResult
from app.providers.mock import DownstreamError
from app.resilience import CircuitBreaker, CircuitOpenError, ResilientPipeline, CircuitState
from uuid import uuid4


def event():
    return CallEvent(event_id=uuid4(), campaign_id="C", borrower_bucket="0-30 DPD", timestamp="2026-09-01T00:00:00Z", outcome="connected")


class Provider:
    def __init__(self, errors=0, permanent=False): self.errors, self.calls, self.permanent = errors, 0, permanent
    async def process(self, _):
        self.calls += 1
        if self.calls <= self.errors: raise DownstreamError("boom", transient=not self.permanent)
        return PipelineResult(status="ok", transcript="x", response_audio_ref="x", latency_ms=1)


@pytest.mark.asyncio
async def test_retry_backoff_and_max_attempts():
    provider, delays = Provider(2), []
    resilient = ResilientPipeline(provider, 3, 1, 10, 0, CircuitBreaker(3, 10), sleep_fn=lambda d: delays.append(d), random_fn=lambda: 0)
    _, retries = await resilient.process(event())
    assert provider.calls == 3 and retries == 2 and delays == [1, 2]


@pytest.mark.asyncio
async def test_permanent_error_not_retried():
    provider = Provider(5, permanent=True)
    resilient = ResilientPipeline(provider, 3, 1, 10, 0, CircuitBreaker(3, 10), sleep_fn=lambda _: None)
    with pytest.raises(DownstreamError): await resilient.process(event())
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_circuit_open_half_open_close_and_reject():
    now = [0.0]
    breaker = CircuitBreaker(2, 5, time_fn=lambda: now[0])
    provider = Provider(2)
    resilient = ResilientPipeline(provider, 1, 0, 1, 0, breaker, sleep_fn=lambda _: None)
    for _ in range(2):
        with pytest.raises(DownstreamError): await resilient.process(event())
    assert breaker.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError): await resilient.process(event())
    assert provider.calls == 2
    now[0] = 6
    await resilient.process(event())
    assert breaker.state == CircuitState.CLOSED
