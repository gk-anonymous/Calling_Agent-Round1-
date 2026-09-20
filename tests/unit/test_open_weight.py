import pytest

from app.domain.models import CallEvent
from app.providers.open_weight import OpenWeightPipelineProvider
from uuid import uuid4


def event():
    return CallEvent(event_id=uuid4(), campaign_id="C", borrower_bucket="0-30 DPD", timestamp="2026-09-01T00:00:00Z", outcome="connected")


@pytest.mark.asyncio
async def test_open_weight_provider_composes_three_stages():
    calls = []

    async def stt(payload):
        calls.append("stt")
        return {"transcript": "hello", "latency_ms": 10}

    async def llm(payload):
        calls.append(("llm", payload["transcript"]))
        return {"text": "please pay", "latency_ms": 20}

    async def tts(payload):
        calls.append(("tts", payload["text"]))
        return {"audio_ref": "synthetic-audio", "latency_ms": 30}

    result = await OpenWeightPipelineProvider(stt, llm, tts).process(event())
    assert result.transcript == "hello"
    assert result.response_audio_ref == "synthetic-audio"
    assert result.latency_ms == 60
    assert calls == ["stt", ("llm", "hello"), ("tts", "please pay")]