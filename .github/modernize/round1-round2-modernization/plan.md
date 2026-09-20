# Modernization Plan: Round 1 and Round 2 Challenge Completion

**Project**: Collections Voice-Agent Inference Service

## Technical Framework

- **Language**: Python 3.12+ (repository documentation requirement)
- **Framework**: FastAPI with Uvicorn
- **Build Tool**: pip and pytest
- **Database**: SQLite local default; planned DynamoDB durable AWS DLQ records
- **Messaging**: Planned SQS replay/event references; existing Terraform queue
- **Runtime**: Docker locally; AWS ECS Fargate in ap-south-1
- **Observability**: FastAPI metrics endpoint, structured logs, CloudWatch Logs/Metrics
- **Provider boundary**: Existing protocol and mock HTTP provider; planned open-weight adapter

## Overview

This plan completes the remaining Round 1 and Round 2 challenge requirements without
executing application changes or infrastructure. The checked-out service already has
retry, circuit-breaker, local SQLite DLQ, a mock provider, and Terraform definitions
for an AWS deployment. The implementation work will close the gaps between those local
capabilities and the AWS/runtime challenge requirements.

The resulting implementation will:

- expose and publish latency percentiles, traffic, failures, retries, DLQ depth, and
  autoscaling signals without fabricating exact final 80/20 results;
- keep SQLite as the zero-credential local default while integrating DynamoDB and SQS
  for durable AWS DLQ records and replay references;
- add an open-weight STT -> LLM -> TTS provider boundary that reuses the current
  resilience behavior and works on CPU or a separately approved GPU option;
- document and test controlled dependency failures, recovery, circuit breaking, DLQ,
  replay, cost, operations, and evidence capture.

The work is phased as baseline capture, sequential application changes, an explicit
GPU deployment option, controlled integration validation, security review, and evidence
and documentation completion. No AWS GPU resources are provisioned by this plan.

## Migration Impact Summary

| Application   | Original Service          | New Service/Capability             | Authentication                     | Comments                           |
| ------------- | ------------------------- | ---------------------------------- | ---------------------------------- | ---------------------------------- |
| Inference API | Process-local metrics     | CloudWatch metrics and API metrics | ECS task IAM role                  | Preserve local metrics for tests   |
| Inference API | SQLite-only DLQ           | DynamoDB plus SQS on AWS           | Least-privilege task IAM           | SQLite remains local default       |
| Inference API | Mock single-call provider | Open-weight STT/LLM/TTS adapter    | Configured local/internal endpoint | Resilience remains outside adapter |
| Demo runtime  | Fargate-only compute      | Documented EC2 g5.xlarge option    | Explicit approval required         | Prefer ap-south-1; no provisioning |

## Scope and Constraints

- Target AWS region for the option and existing deployment context: `ap-south-1`.
- Do not execute the plan, provision infrastructure, download models, or require a GPU.
- Preserve existing retry, backoff, circuit-breaker, idempotency, and DLQ decisions.
- Keep SQLite as the local default and make AWS backend selection explicit by config.
- Use IAM least privilege for DynamoDB, SQS, CloudWatch, and related task actions.
- Replay must update durable status correctly for success, failure, duplicate, and retry
  paths, including concurrency-safe claim/release behavior.
- A configured 20% per-attempt dependency failure rate is a demo input, not proof that
  final outcomes are exactly 80% success and 20% failure. Evidence must report observed
  samples and confidence/limitations.
- The open-weight shortlist is faster-whisper for STT, Mistral or Llama for LLM, and
  Piper for TTS. The adapter may use real local/internal services or a deterministic
  real-shaped boundary when model execution is unavailable, but must not bypass the
  provider contract or resilience layer.
- GPU work is an option/plan only. Prefer documenting EC2 `g5.xlarge` in `ap-south-1`,
  CPU fallback behavior, costs, operational prerequisites, and approval gates.

## Risks and Mitigations

- **Cloud/local behavior diverges**: use repository-contract tests against fake AWS
  clients and a deployed integration checklist before claiming completion.
- **At-least-once replay duplicates work**: preserve processed-event idempotency and use
  conditional durable state transitions; test concurrent replay and duplicate delivery.
- **Metric cardinality or missing dimensions**: define a bounded metric taxonomy and
  validate API, logs, CloudWatch, and autoscaling visibility separately.
- **CPU open-weight latency is unsuitable**: keep provider execution configurable, record
  observed latency and model profile, and document CPU as fallback rather than GPU-track
  equivalence.
- **GPU cost or availability surprises**: make the g5 option non-default and require
  explicit approval, quota/region confirmation, and a destroy/rollback procedure.
- **Failure demos overclaim results**: retain raw counts, attempt-level failures, retry
  outcomes, circuit transitions, and DLQ/replay records; never assert an exact ratio.

## Acceptance and Traceability

The task file is the executable work breakdown. Each task includes acceptance criteria,
dependencies, and links to the numbered requirements in the user request. The final
acceptance gate requires tests, runbook/README/cost updates, and a demo evidence bundle
covering both local SQLite and AWS-configured paths without executing provisioning in
this planning phase.

## Open Questions & Questionnaire

- [ ] Confirm the exact open-weight model licenses and approved model endpoints before
      selecting downloadable model artifacts.
- [ ] Confirm whether the GPU-track evaluator requires an actual GPU run or accepts a
      documented, approval-gated deployment option for this round.
- [ ] Confirm AWS account-specific g5.xlarge quota and availability in `ap-south-1`
      before any future provisioning request.
- [ ] Confirm the preferred CloudWatch dashboard namespace and retention period if the
      challenge evaluator requires values different from the existing Terraform defaults.

## Out of Scope for This Plan

- Executing pytest, Terraform, Docker, AWS CLI, model downloads, or deployments.
- Provisioning or modifying the AWS stack, including EC2 GPU resources.
- Claiming production-grade model quality, exact traffic distribution, or exact 80/20
  final outcomes from a probabilistic per-attempt failure configuration.
