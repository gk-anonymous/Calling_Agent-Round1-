# Runbook: Collections Voice-Agent Inference Service

## Trigger

Investigate when p99 latency exceeds three times the normal baseline or failed downstream calls rise during a campaign.

## First five minutes

1. Check `/metrics` for request rate, error rate, latency samples, DLQ depth, and circuit counters.
2. Check mock or provider logs for 503s, timeouts, and retry entries.
3. Check `/health` for the circuit state. `OPEN` means calls are being degraded to the DLQ instead of repeatedly hitting a dead dependency.

The metrics endpoint reports `latency_p50_ms`, `latency_p90_ms`, `latency_p95_ms`, and `latency_p99_ms`. Report observed values with the sample count; the 20% dependency setting is per attempt, not an exact final failure percentage.

For a controlled demo, run `python scripts/demo_failure.py --base-url URL --count 10` after setting the dependency failure mode through the deployment configuration. Capture raw responses, retry counts, final failures, circuit transitions, DLQ depth, and replay results. Do not claim an exact 80/20 final ratio.

## Downstream incident

Confirm retries are bounded and the circuit has opened. Inspect `/dlq`; records must contain the original payload and retry count. After recovery, replay one event first with `python scripts/replay_dlq.py --event-id ID`, then use `--pending` for the remainder.

## Post-incident

Record actual latency and failure percentages, confirm replayed records are `RESOLVED`, and remove `data/live.sqlite3` only when the evidence is no longer needed.
