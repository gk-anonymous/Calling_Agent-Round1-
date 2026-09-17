# Collections Voice-Agent Inference Service

Round 1 local submission for the Predixion AI x TalentX Open-Weight Collections Agent Challenge. This is a synthetic-only FastAPI service: it retries transient provider failures, opens a circuit when logical requests fail, persists exhausted work in SQLite, and supports safe replay.

## Architecture
<img width="1536" height="1024" alt="ChatGPT Image Sep 17, 2026, 02_49_13 AM" src="https://github.com/user-attachments/assets/9fd9260b-287f-4854-a836-26dc1a4ed0c5" />


The provider makes one downstream call. Resilience owns retries, and the application owns orchestration and DLQ decisions. Circuit failures count once per logical event after all of that event's retry attempts are exhausted; circuit rejection is an immediate logical failure and is not retried.

## Quick start

Prerequisite: Python 3.12+ and pip. From a clean checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS/Linux, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Start two terminals:

```powershell
python -m uvicorn mock_service:app --port 8001
python main.py
```

The inference API is at `http://localhost:8000`; the unreliable mock is at `http://localhost:8001`. Docker users can run `docker compose up --build`, then `docker compose down`.

No credentials, cloud account, database server, model download, console setup, or manual database migration is required. The application creates `data/dlq.sqlite3` on first start.

## API

`POST /events/process` accepts the challenge event schema and returns success, outcome, retry count, circuit state, downstream latency, total latency, and DLQ status. `GET /health` checks service health. `GET /metrics` returns local counters and recent request latency. `GET /dlq` lists records; `GET /dlq/{event_id}` inspects one. `POST /dlq/{event_id}/replay` replays one event through the normal processing path; `POST /dlq/replay-pending` replays all pending or failed records.

## Configuration and behavior

Copy `.env.example` to `.env`. `MAX_ATTEMPTS`, backoff delays, jitter, circuit threshold/recovery timeout, downstream URL, failure rate, and lognormal latency parameters are configurable. The default sigma is `0.55`, calibrated from the specified `0.35` starting point to put p90/p99 nearer the challenge targets while retaining a p50 near 300 ms. No secrets are needed or accepted. Retries apply only to HTTP 503, timeouts, and connection errors. Permanent HTTP errors and invalid provider responses are not retried. Structured event logs include event/campaign IDs, success, latencies, retry count, circuit state, final outcome, and DLQ status; retry logs include event ID, attempt, maximum attempts, delay, and error.

The DLQ is `data/dlq.sqlite3` by default and survives process restarts. It stores the original payload, failure timestamps/reason, retry count, replay count, status, and last error. Event IDs are primary keys, and a separate processed-event table prevents duplicate successful downstream processing. Statuses are `PENDING`, `REPLAYING`, `FAILED`, and `RESOLVED`.

## Traffic and latency checks

The exact profile is encoded in `scripts/generate_traffic.py`: 10 calls/min baseline; 08:00-10:00 and 14:00-16:00 campaigns ramp 10 to 50 over 15 simulated minutes and hold at 50. Compression is controlled by simulated minutes per real minute. Use `--start-hour 8 --duration-seconds 2 --speed 60` to demonstrate the first campaign ramp without waiting for simulated midnight, or use `--start-hour 0 --duration-seconds 1440 --speed 60` for a full compressed day. The script uses concurrent requests and prints target rates plus a final summary. Check the starting latency distribution with `python scripts/latency_test.py --samples 5000`.

Inspect/replay from the shell with `python scripts/inspect_dlq.py`, `python scripts/inspect_dlq.py --event-id ID`, `python scripts/replay_dlq.py --event-id ID`, or `python scripts/replay_dlq.py --pending`.

## Submission checklist

From the project directory, verify the clean source tree before publishing:

```powershell
python -m pytest -q
Get-ChildItem -Recurse -File | Where-Object {$_.FullName -notmatch '\\.pytest_cache|__pycache__|\\data'}
```

Publish the contents of this directory to a public GitHub repository. Include the source, tests, README, runbook, cost analysis, Docker files, requirements, `.env.example`, and `LICENSE`. Do not commit `.env`, `data/`, SQLite files, virtual environments, caches, or real borrower data. A reviewer can then clone the repository and follow the Quick start section exactly.

If a port is already in use, stop the existing process or start the mock and inference services on different ports and update `DOWNSTREAM_URL` accordingly. The default commands use ports `8000` and `8001`.

## Testing

Run `python -m pytest -q`. Tests use fake providers, injected sleep, and deterministic clocks where timing matters; they do not depend on random mock failures. Coverage includes retry limits/backoff/jitter, permanent errors, all circuit states, DLQ restart/replay/idempotency, processor integration, and traffic target-rate/ramp/hold helpers.

## Open-weight migration

`MockPipelineProvider` can be replaced by an `OpenWeightPipelineProvider` that makes one local or internal call to faster-whisper large-v3/large-v3-turbo for STT, Mistral-7B-Instruct-v0.3 or Llama-3.1-8B-Instruct for the LLM, and Piper or Coqui XTTS-v2 for TTS. Only the provider adapter and its response mapping change; retry, circuit breaker, DLQ, orchestration, and observability remain unchanged. Review each model's license and usage terms before public Apache 2.0 release.

## Limitations and security

This local implementation uses synchronous SQLite access inside async request handlers, appropriate for the challenge scale but not a high-volume production database. Metrics are process-local and logs use the standard logger rather than a full telemetry backend. All payloads are synthetic, request validation is strict, and there are no credentials, borrower identifiers, audio files, or external cloud dependencies.

## Cost

See [COST_ANALYSIS.md](COST_ANALYSIS.md) for independent Config A/B calculations and fixed ALB/NAT overhead discussion. Round 1 does not deploy AWS infrastructure.

## License

Apache 2.0. This repository contains only synthetic challenge data and code intended for public release.
