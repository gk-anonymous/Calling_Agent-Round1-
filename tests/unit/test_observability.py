from app.observability import Metrics


def test_metrics_expose_rates_and_percentiles():
    metrics = Metrics()
    for value in [10, 20, 30, 40, 50]:
        metrics.inc("requests_total")
        metrics.inc("requests_success_total")
        metrics.observe(value)

    snapshot = metrics.snapshot()
    assert snapshot["request_success_rate"] == 1.0
    assert snapshot["request_error_rate"] == 0.0
    assert snapshot["latency_p50_ms"] == 30
    assert snapshot["latency_p90_ms"] == 46
    assert snapshot["latency_p95_ms"] == 48
    assert snapshot["latency_p99_ms"] == 49.6


def test_metrics_bound_latency_samples():
    metrics = Metrics(max_latency_samples=2)
    metrics.observe(1)
    metrics.observe(2)
    metrics.observe(3)
    assert metrics.latencies == [2, 3]