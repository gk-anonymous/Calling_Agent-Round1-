import logging
from app.domain.models import CallEvent, ProcessResponse
from app.observability import Metrics, monotonic_ms
from app.resilience import CircuitOpenError, ResilientPipeline

logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(self, resilient: ResilientPipeline, dlq, metrics: Metrics):
        self.resilient = resilient
        self.dlq = dlq
        self.metrics = metrics

    async def process(self, event: CallEvent) -> ProcessResponse:
        started = monotonic_ms()
        self.metrics.inc("requests_total")
        if not self.dlq.claim_event(str(event.event_id)):
            return ProcessResponse(event_id=event.event_id, success=True, outcome=event.outcome, retry_count=0,
                                   circuit_state=self.resilient.breaker.state.value, total_latency_ms=0)
        try:
            result, retries = await self.resilient.process(event)
            self.dlq.mark_processed(str(event.event_id))
            self.metrics.inc("requests_success_total")
            self.metrics.inc("retry_total", retries)
            total = monotonic_ms() - started
            self.metrics.observe(total)
            logger.info("event_processed", extra={"event_id": str(event.event_id), "campaign_id": event.campaign_id, "success": True, "downstream_latency_ms": result.latency_ms, "total_latency_ms": total, "retry_count": retries, "circuit_state": self.resilient.breaker.state.value, "final_outcome": event.outcome})
            return ProcessResponse(event_id=event.event_id, success=True, outcome=event.outcome, retry_count=retries, circuit_state=self.resilient.breaker.state.value, downstream_latency_ms=result.latency_ms, total_latency_ms=total)
        except Exception as exc:
            self.dlq.release_event(str(event.event_id))
            self.metrics.inc("requests_failed_total")
            if isinstance(exc, CircuitOpenError):
                self.metrics.inc("circuit_rejected_total")
                self.metrics.inc("circuit_open_total")
            else:
                self.metrics.inc("downstream_failures_total")
            retries = getattr(exc, "retry_count", 0)
            self.metrics.inc("retry_total", retries)
            row = self.dlq.enqueue(event, str(exc), retries)
            self.metrics.inc("dlq_enqueued_total")
            total = monotonic_ms() - started
            self.metrics.observe(total)
            logger.error("event_failed", extra={"event_id": str(event.event_id), "campaign_id": event.campaign_id, "success": False, "total_latency_ms": total, "retry_count": retries, "circuit_state": self.resilient.breaker.state.value, "final_outcome": "failed_downstream", "dlq_status": row["status"]})
            return ProcessResponse(event_id=event.event_id, success=False, outcome="failed_downstream", retry_count=retries, circuit_state=self.resilient.breaker.state.value, total_latency_ms=total, dlq_status=row["status"])

    async def replay(self, event_id: str):
        row = self.dlq.begin_replay(event_id)
        if not row:
            return None
        response = await self.process(self.dlq.decode_event(row))
        self.dlq.finish_replay(event_id, response.success, "" if response.success else response.outcome)
        self.metrics.inc("dlq_replay_total")
        return response
