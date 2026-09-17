# Runbook: Collections Voice-Agent Inference Service

## Trigger

Investigate when p99 latency exceeds three times the normal baseline or failed downstream calls rise during a campaign.

## First five minutes

1. Check `/metrics` for request rate, error rate, latency samples, DLQ depth, and circuit counters.
2. Check mock or provider logs for 503s, timeouts, and retry entries.
3. Check `/health` for the circuit state. `OPEN` means calls are being degraded to the DLQ instead of repeatedly hitting a dead dependency.

## Downstream incident

Confirm retries are bounded and the circuit has opened. Inspect `/dlq`; records must contain the original payload and retry count. After recovery, replay one event first with `python scripts/replay_dlq.py --event-id ID`, then use `--pending` for the remainder.

## Post-incident

Record actual latency and failure percentages, confirm replayed records are `RESOLVED`, and remove `data/live.sqlite3` only when the evidence is no longer needed.
