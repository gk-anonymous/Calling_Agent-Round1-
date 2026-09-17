import logging
import time
from collections import Counter


class Metrics:
    def __init__(self):
        self.counters = Counter({name: 0 for name in (
            "requests_total", "requests_success_total", "requests_failed_total",
            "downstream_failures_total", "retry_total", "circuit_open_total",
            "circuit_rejected_total", "dlq_enqueued_total", "dlq_replay_total")})
        self.latencies: list[float] = []

    def inc(self, name: str, amount: int = 1):
        self.counters[name] += amount

    def observe(self, value: float):
        self.latencies.append(value)

    def snapshot(self):
        return {**self.counters, "request_latency_ms": self.latencies[-1000:]}


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def monotonic_ms():
    return time.perf_counter() * 1000
