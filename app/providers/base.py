from typing import Protocol

from app.domain.models import CallEvent, PipelineResult


class PipelineProvider(Protocol):
    async def process(self, event: CallEvent) -> PipelineResult:
        """Make exactly one downstream pipeline call for an event."""
