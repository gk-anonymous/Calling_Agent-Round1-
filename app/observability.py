import logging
import time
from collections import Counter
from collections.abc import Callable


class Metrics:
    def __init__(self, max_latency_samples: int = 1000, publisher: Callable[[dict], None] | None = None):
        self.max_latency_samples = max_latency_samples
        self.publisher = publisher
        self.counters = Counter({name: 0 for name in (
            "requests_total", "requests_success_total", "requests_failed_total",
            "downstream_failures_total", "retry_total", "circuit_open_total",
            "circuit_rejected_total", "dlq_enqueued_total", "dlq_replay_total")})
        self.latencies: list[float] = []

    def inc(self, name: str, amount: int = 1):
        self.counters[name] += amount

    def observe(self, value: float):
        self.latencies.append(value)
        if len(self.latencies) > self.max_latency_samples:
            del self.latencies[:-self.max_latency_samples]
        if self.publisher:
            self.publisher(self.snapshot())

    def percentile(self, percentile: float) -> float | None:
        if not self.latencies:
            return None
        values = sorted(self.latencies)
        position = (len(values) - 1) * percentile / 100
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        return round(values[lower] + (values[upper] - values[lower]) * fraction, 2)

    def snapshot(self):
        total = self.counters["requests_total"]
        return {
            **self.counters,
            "request_success_rate": round(self.counters["requests_success_total"] / total, 4) if total else 0.0,
            "request_error_rate": round(self.counters["requests_failed_total"] / total, 4) if total else 0.0,
            "retry_rate": round(self.counters["retry_total"] / total, 4) if total else 0.0,
            "latency_p50_ms": self.percentile(50),
            "latency_p90_ms": self.percentile(90),
            "latency_p95_ms": self.percentile(95),
            "latency_p99_ms": self.percentile(99),
            "request_latency_ms": self.latencies,
        }


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def cloudwatch_publisher(namespace: str, service_name: str, region: str):
    import boto3

    client = boto3.client("cloudwatch", region_name=region)

    def publish(snapshot: dict):
        total = snapshot["requests_total"]
        metrics = [
            ("RequestsTotal", total, "Count"),
            ("RequestsSuccess", snapshot["requests_success_total"], "Count"),
            ("RequestsFailed", snapshot["requests_failed_total"], "Count"),
            ("RetryTotal", snapshot["retry_total"], "Count"),
            ("InFlightCalls", 0, "Count"),
        ]
        for name in ("latency_p50_ms", "latency_p90_ms", "latency_p95_ms", "latency_p99_ms"):
            if snapshot[name] is not None:
                metrics.append((name, snapshot[name], "Milliseconds"))
        client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {"MetricName": name, "Value": value, "Unit": unit, "Dimensions": [{"Name": "Service", "Value": service_name}]}
                for name, value, unit in metrics
            ],
        )

    return publish


def monotonic_ms():
    return time.perf_counter() * 1000
