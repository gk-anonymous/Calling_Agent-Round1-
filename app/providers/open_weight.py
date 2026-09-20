from collections.abc import Awaitable, Callable

from app.domain.models import CallEvent, PipelineResult
from app.providers.mock import DownstreamError


Stage = Callable[[dict], Awaitable[dict]]


class OpenWeightPipelineProvider:
    """Adapter for an STT -> LLM -> TTS open-weight model gateway.

    The gateway may host faster-whisper, Mistral/Llama, and Piper/XTTS. Keeping
    the three stages behind this adapter means resilience remains unchanged.
    """

    def __init__(self, stt: Stage, llm: Stage, tts: Stage):
        self.stt = stt
        self.llm = llm
        self.tts = tts

    async def process(self, event: CallEvent) -> PipelineResult:
        try:
            transcription = await self.stt({"event_id": str(event.event_id), "audio_ref": "synthetic"})
            prompt = await self.llm({"event_id": str(event.event_id), "transcript": transcription["transcript"]})
            audio = await self.tts({"event_id": str(event.event_id), "text": prompt["text"]})
            return PipelineResult(
                status="ok",
                transcript=transcription["transcript"],
                response_audio_ref=audio["audio_ref"],
                latency_ms=float(transcription.get("latency_ms", 0))
                + float(prompt.get("latency_ms", 0))
                + float(audio.get("latency_ms", 0)),
            )
        except KeyError as exc:
            raise DownstreamError(f"invalid_open_weight_response:{exc}", transient=False) from exc
        except DownstreamError:
            raise
        except Exception as exc:
            raise DownstreamError("open_weight_stage_unavailable", transient=True) from exc