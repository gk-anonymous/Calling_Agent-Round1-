import httpx

from app.domain.models import CallEvent, PipelineResult


class DownstreamError(Exception):
    def __init__(self, message: str, *, transient: bool = True):
        super().__init__(message)
        self.transient = transient


class MockPipelineProvider:
    def __init__(self, base_url: str, timeout: float = 5.0, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = client

    async def process(self, event: CallEvent) -> PipelineResult:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(
                f"{self.base_url}/pipeline/process",
                json={"event_id": str(event.event_id), "audio_ref": "synthetic"},
            )
            if response.status_code == 503:
                raise DownstreamError("downstream_timeout", transient=True)
            if response.status_code >= 400:
                raise DownstreamError(f"downstream_http_{response.status_code}", transient=False)
            try:
                return PipelineResult.model_validate(response.json())
            except Exception as exc:
                raise DownstreamError("invalid_downstream_response", transient=False) from exc
        except httpx.TimeoutException as exc:
            raise DownstreamError("downstream_timeout", transient=True) from exc
        except httpx.RequestError as exc:
            raise DownstreamError("downstream_unavailable", transient=True) from exc
        finally:
            if owns_client:
                await client.aclose()
