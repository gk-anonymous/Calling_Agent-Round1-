import asyncio
import inspect
import logging
import random
import time
from enum import Enum
from typing import Awaitable, Callable

from app.providers.mock import DownstreamError

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, threshold: int, recovery_timeout: float, probes: int = 1,
                 time_fn: Callable[[], float] = time.monotonic):
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.probes = probes
        self.time_fn = time_fn
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at: float | None = None
        self.active_probes = 0

    def _transition(self, state: CircuitState, event_id: str | None = None) -> None:
        if self.state != state:
            logger.info("circuit_state_transition", extra={"from_state": self.state.value, "to_state": state.value, "event_id": event_id})
            self.state = state

    def allow(self, event_id: str | None = None) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN and self.opened_at is not None and self.time_fn() - self.opened_at >= self.recovery_timeout:
            self._transition(CircuitState.HALF_OPEN, event_id)
            self.active_probes = 0
        if self.state == CircuitState.HALF_OPEN and self.active_probes < self.probes:
            self.active_probes += 1
            return True
        logger.info("circuit_request_rejected", extra={"event_id": event_id, "state": self.state.value})
        return False

    def success(self, event_id: str | None = None) -> None:
        was_probe = self.state == CircuitState.HALF_OPEN
        self.failure_count = 0
        self.active_probes = max(0, self.active_probes - 1)
        if was_probe:
            self._transition(CircuitState.CLOSED, event_id)
            logger.info("circuit_successful_probe", extra={"event_id": event_id})

    def failure(self, event_id: str | None = None) -> None:
        was_probe = self.state == CircuitState.HALF_OPEN
        self.active_probes = max(0, self.active_probes - 1)
        if was_probe or self.failure_count + 1 >= self.threshold:
            self.failure_count = self.threshold if was_probe else self.failure_count + 1
            self.opened_at = self.time_fn()
            self._transition(CircuitState.OPEN, event_id)
        else:
            self.failure_count += 1


class ResilientPipeline:
    def __init__(self, provider, max_attempts: int, initial_delay: float, max_delay: float, jitter_ratio: float,
                 breaker: CircuitBreaker, sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 random_fn: Callable[[], float] = random.random):
        self.provider = provider
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter_ratio = jitter_ratio
        self.breaker = breaker
        self.sleep_fn = sleep_fn
        self.random_fn = random_fn

    async def process(self, event):
        if not self.breaker.allow(str(event.event_id)):
            raise CircuitOpenError("circuit_open")
        retry_count = 0
        while True:
            try:
                result = await self.provider.process(event)
                self.breaker.success(str(event.event_id))
                return result, retry_count
            except DownstreamError as exc:
                if not exc.transient or retry_count >= self.max_attempts - 1:
                    exc.retry_count = retry_count
                    self.breaker.failure(str(event.event_id))
                    raise
                retry_count += 1
                base = min(self.max_delay, self.initial_delay * (2 ** (retry_count - 1)))
                delay = base * (1 + self.jitter_ratio * self.random_fn())
                logger.warning("downstream_retry", extra={"event_id": str(event.event_id), "attempt": retry_count, "max_attempts": self.max_attempts, "delay": delay, "error": str(exc)})
                sleep_result = self.sleep_fn(delay)
                if inspect.isawaitable(sleep_result):
                    await sleep_result
