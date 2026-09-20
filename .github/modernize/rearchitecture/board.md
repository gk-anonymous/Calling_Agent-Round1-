## User Input

> Execute the approved modernization plan for workspace d:/Calling_Agent. Use plan d:/Calling_Agent/.github/modernize/round1-round2-modernization/plan.md and tasks d:/Calling_Agent/.github/modernize/round1-round2-modernization/.metadata/tasks.json as the source of truth. Execute every task in dependency order, including baseline capture; observability for p50/p90/p95/p99 plus request/error/retry/DLQ/autoscaling metrics; DynamoDB/SQS DLQ integration with SQLite local fallback; open-weight provider boundary and real-shaped STT -> LLM -> TTS option while preserving resilience logic; GPU g5.xlarge only behind explicit approval and never provision or leave it running without clear prerequisite approval; controlled failure/retry/circuit/DLQ/replay tests and demo docs; integration validation; IAM/dependency security review. Preserve unrelated user changes, do not commit unless the plan explicitly requires it, and leave existing AWS resources unchanged unless a task explicitly requires a safe update. Do not claim GPU or open-weight runtime completion if dependencies, licenses, quota, or hardware are unavailable. Report each task outcome, files changed, tests/build results, AWS resources changed, and blockers. Continue through all feasible tasks and return a concise execution summary with evidence.

**Project started**: 2026-09-19T15:23:02.2921889Z

## Tasks

### Phase: Baseline

- 🔄 001-setup-baseline [analyst] Capture current local and AWS-shaped behavior before modernization

### Phase: Observability

- ⏳ 002-transform-observability-and-autoscaling [backend] Expose complete latency, traffic, failure, retry, DLQ, and autoscaling visibility [deps: 001-setup-baseline]

### Phase: AWS DLQ

- ⏳ 003-transform-aws-dlq-integration [backend] Integrate durable AWS DLQ backend while retaining SQLite local default [deps: 002-transform-observability-and-autoscaling]

### Phase: Provider

- ⏳ 004-transform-open-weight-provider-boundary [backend] Add configurable open-weight STT to LLM to TTS provider path behind existing resilience boundary [deps: 003-transform-aws-dlq-integration]

### Phase: Infrastructure option

- ⏳ 005-infrastructure-gpu-option-plan [infrastructure] Document approval-gated g5.xlarge GPU deployment option and CPU fallback [deps: 004-transform-open-weight-provider-boundary]

### Phase: Evidence and docs

- ⏳ 006-transform-demo-evidence-and-documentation [tester] Update tests, operational documentation, cost analysis, and demo evidence requirements [deps: 005-infrastructure-gpu-option-plan]

### Phase: Integration validation

- ⏳ 007-integrationTest-round1-round2-validation [tester] Run post-change local and AWS-shaped verification [deps: 001-setup-baseline, 002-transform-observability-and-autoscaling, 003-transform-aws-dlq-integration, 004-transform-open-weight-provider-boundary, 005-infrastructure-gpu-option-plan, 006-transform-demo-evidence-and-documentation]

### Phase: Security review

- ⏳ 008-security-iam-and-dependency-review [security] Review least-privilege AWS access, model/provider supply chain, and dependency security [deps: 007-integrationTest-round1-round2-validation]
