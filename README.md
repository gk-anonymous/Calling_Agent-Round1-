
# Collections Voice-Agent Inference Service



This project implements a resilient voice-agent inference service around an unreliable STT → LLM → TTS-style downstream dependency.

The system demonstrates:

* Retry with exponential backoff and jitter
* Circuit breaker
* Dead-letter queue (DLQ)
* Idempotent event processing
* Safe DLQ replay
* Model/provider abstraction
* Request, error, retry and circuit metrics
* p50/p90/p95/p99 latency metrics
* AWS deployment using Terraform
* ECS Fargate behind an Application Load Balancer
* DynamoDB + SQS-backed AWS DLQ
* CloudWatch observability
* Production-oriented infrastructure and failure handling

---

## Architecture

```text
                         Client
                           |
                           v
                    Application Load
                       Balancer
                           |
                           v
                 ECS Fargate / FastAPI
                           |
                           v
                    Event Processor
                           |
                           v
                 Resilience Layer
                 /               \
          Retry + Backoff     Circuit Breaker
                 \               /
                           |
                           v
                    Provider Interface
                    /                 \
                   /                   \
          Mock Provider          Open-Weight Adapter
                   |                   |
                   v                   v
             Mock STT → LLM → TTS   STT → LLM → TTS


Failed logical events
          |
          v
         DLQ
       /     \
 SQLite       AWS
(local)   DynamoDB + SQS
```

The provider interface keeps model-specific inference separate from resilience and orchestration logic.

This allows the downstream implementation to be replaced without changing retry, circuit-breaker, idempotency, DLQ, or observability logic.

---

## Quick Start

### Clone

```bash
git clone https://github.com/gk-anonymous/Calling_Agent-Round1-.git
cd Calling_Agent-Round1-
```

### Prerequisites

* Python 3.12+
* pip
* Docker (optional)

No cloud account is required for local execution.

---

## Local Setup

### Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

---

## Start Locally

Start the unreliable mock dependency in Terminal 1:

```bash
python -m uvicorn mock_service:app --port 8001
```

Start the inference API in Terminal 2:

```bash
python main.py
```

The inference API is available at:

```text
http://localhost:8000
```

The unreliable mock dependency is available at:

```text
http://localhost:8001
```

The application automatically creates the local SQLite database:

```text
data/dlq.sqlite3
```

No manual database migration or external database setup is required.

---

## Docker

Build and start the complete local stack:

```bash
docker compose up --build
```

Stop the stack:

```bash
docker compose down
```

---

# Deployed AWS Endpoints

The service is also deployed on AWS in the `ap-south-1` region behind an Application Load Balancer.

### Health

**Live endpoint:**

[http://collections-challenge-demo-722200242.ap-south-1.elb.amazonaws.com/health](http://collections-challenge-demo-722200242.ap-south-1.elb.amazonaws.com/health)

The endpoint reports service health and circuit-breaker state.

### Metrics

**Live endpoint:**

[http://collections-challenge-demo-722200242.ap-south-1.elb.amazonaws.com/metrics](http://collections-challenge-demo-722200242.ap-south-1.elb.amazonaws.com/metrics)

The endpoint exposes application metrics including:

* Total requests
* Successful requests
* Failed requests
* Downstream failures
* Retry count
* Circuit openings
* Circuit rejections
* DLQ enqueue count
* DLQ replay count
* Success rate
* Error rate
* Retry rate
* p50 latency
* p90 latency
* p95 latency
* p99 latency

---

# API

## Process Event

```http
POST /events/process
```

Processes a collections event through the normal inference pipeline.

The response includes:

```text
event_id
success
outcome
retry_count
circuit_state
downstream_latency_ms
total_latency_ms
dlq_status
```

Example:

```bash
curl -X POST http://localhost:8000/events/process \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "demo-001",
    "campaign_id": "campaign-001",
    "payload": {
      "customer_id": "customer-001"
    }
  }'
```

---

## Health

```http
GET /health
```

Returns service health and circuit state.

---

## Metrics

```http
GET /metrics
```

Returns application metrics and latency percentiles.

---

## DLQ

List DLQ records:

```http
GET /dlq
```

Inspect a specific event:

```http
GET /dlq/{event_id}
```

Replay a specific event:

```http
POST /dlq/{event_id}/replay
```

Replay all pending/failed events:

```http
POST /dlq/replay-pending
```

---

# Resilience

The service treats a complete event as the unit of resilience.

Transient dependency failures such as:

* HTTP 503
* Connection errors
* Timeouts

are retried using configurable exponential backoff and jitter.

The logical event is counted as one failure only after its retry attempts are exhausted.

The circuit breaker protects the service when the downstream dependency remains unavailable.

Circuit states:

```text
CLOSED
   |
   | failure threshold reached
   v
OPEN
   |
   | recovery timeout
   v
HALF_OPEN
   |
   | successful probe
   v
CLOSED
```

When the circuit is open, requests are rejected immediately rather than repeatedly calling an unhealthy dependency.

---

# Retry Strategy

The retry layer supports:

* Configurable maximum attempts
* Exponential backoff
* Maximum backoff limit
* Random jitter
* Retryable HTTP errors
* Connection errors
* Timeout handling

Retries are intentionally applied only to transient failures.

Permanent errors and invalid provider responses are not blindly retried.

---

# Dead-Letter Queue

Failed events that cannot be completed after the resilience policy are persisted to the DLQ.

### Local

Local development uses:

```text
SQLite
```

### AWS

The AWS deployment uses:

```text
DynamoDB
    +
SQS
```

DynamoDB stores durable DLQ records and processing state.

SQS stores event references for asynchronous handling.

Replay sends the event back through the normal processing path.

This means replay does not bypass:

* Validation
* Idempotency
* Provider invocation
* Retry handling
* Circuit-breaker logic
* Metrics

---

# Idempotency

The processor uses event-level idempotency to prevent duplicate logical processing.

This is important for:

* Retry scenarios
* Client retries
* DLQ replay
* Network failures
* Duplicate delivery

A replayed event is processed safely without creating duplicate logical work.

---

# Observability

The application records:

* Request count
* Successful requests
* Failed requests
* Downstream failures
* Retry count
* Circuit openings
* Circuit rejections
* DLQ enqueue count
* DLQ replay count
* Request latency

Latency percentiles include:

```text
p50
p90
p95
p99
```

The metrics are calculated from a bounded recent request sample.

In AWS mode, completed requests also publish the configured metric taxonomy to CloudWatch.

---

# Example Metrics

A successful traffic run can produce metrics such as:

```text
requests_total
requests_success_total
requests_failed_total
downstream_failures_total
retry_total
circuit_open_total
circuit_rejected_total
dlq_enqueued_total
dlq_replay_total

request_success_rate
request_error_rate
retry_rate

latency_p50_ms
latency_p90_ms
latency_p95_ms
latency_p99_ms
```

Example observed baseline behavior during testing:

```text
Requests:          15
Successful:        15
Failed:             0
Retries:            7
Circuit opens:      0
DLQ events:         0

p50:              ~448 ms
p90:              ~769 ms
p95:              ~973 ms
p99:             ~1162 ms
```

The exact values vary because the downstream mock uses randomized latency and failure behavior.

---

# Controlled Failure Demonstration

The downstream failure rate can be controlled through Terraform.

Normal challenge-like behavior:

```powershell
terraform -chdir=infra/terraform apply `
  -var="image_tag=latest" `
  -var="downstream_failure_rate=0.20" `
  -auto-approve
```

For a controlled 100% dependency failure demonstration:

```powershell
terraform -chdir=infra/terraform apply `
  -var="image_tag=latest" `
  -var="downstream_failure_rate=1.0" `
  -auto-approve
```

With the dependency completely unavailable, the system demonstrates:

1. Retry attempts
2. Exponential backoff
3. Retry exhaustion
4. Circuit opening
5. Immediate circuit rejection
6. DLQ persistence

During validation, the system produced:

```text
4 logical requests
4 failed requests
6 retry attempts
1 circuit opening
1 circuit rejection
4 DLQ records
```

The dependency can then be restored:

```powershell
terraform -chdir=infra/terraform apply `
  -var="image_tag=latest" `
  -var="downstream_failure_rate=0.20" `
  -auto-approve
```

Then replay pending events:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "$URL/dlq/replay-pending"
```

---

# AWS Infrastructure

Infrastructure is defined using Terraform under:

```text
infra/terraform/
```

The deployment includes:

```text
AWS VPC
│
├── Public Subnets
│
├── Private Subnets
│
├── Internet Gateway
│
├── NAT Gateway
│
└── Security Groups


Application
│
├── Application Load Balancer
├── ECS Fargate
├── ECR
└── CloudWatch


DLQ
│
├── DynamoDB
└── SQS


IAM
│
└── Task / execution permissions
```

The application is deployed behind an ALB and the ECS task runs the FastAPI service.

---

# Terraform

Initialize Terraform:

```powershell
terraform -chdir=infra/terraform init
```

Plan:

```powershell
terraform -chdir=infra/terraform plan
```

Apply:

```powershell
terraform -chdir=infra/terraform apply -auto-approve
```

The deployment is parameterized through Terraform variables such as:

```text
image_tag
downstream_failure_rate
AWS region
```

The primary deployment region is:

```text
ap-south-1
```

---

# AWS Verification

Check ECS:

```powershell
aws ecs describe-services `
  --cluster collections-challenge-demo `
  --services collections-challenge-demo `
  --region ap-south-1 `
  --query "services[0].{Status:status,Desired:desiredCount,Running:runningCount,Pending:pendingCount}" `
  --output table
```

Check ALB target health:

```powershell
$TG = aws elbv2 describe-target-groups `
  --names collections-challenge-demo-tg `
  --region ap-south-1 `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text

aws elbv2 describe-target-health `
  --target-group-arn $TG `
  --region ap-south-1 `
  --output table
```

Check application health:

```powershell
Invoke-RestMethod "$URL/health" | ConvertTo-Json
```

---

# CloudWatch

The AWS deployment publishes application observability information to CloudWatch.

The infrastructure also provisions CloudWatch resources used for monitoring the deployed service.

The application metrics cover:

```text
Request rate
Error rate
Retry rate
Latency
Circuit events
DLQ events
```

A CloudWatch dashboard is provisioned by Terraform.

---

# Open-Weight Model Provider Boundary

The application is intentionally designed so that the inference model is not coupled to the resilience layer.

The provider abstraction separates:

```text
Model-specific inference
        from
Application resilience
```

The current repository contains an open-weight provider adapter prepared for a production STT → LLM → TTS pipeline.

Potential open-weight components include:

### STT

```text
faster-whisper
```

### LLM

```text
Llama
Mistral
```

### TTS

```text
Piper
```

The important architectural property is that replacing the provider does not require rewriting:

* Retry logic
* Circuit breaker
* DLQ
* Replay
* Idempotency
* Metrics
* Event orchestration

---

# Current AWS Model Deployment Status

The current AWS deployment uses a **real-shaped/mock provider** for the downstream inference dependency.

The resilience, orchestration, DLQ, observability, networking, and Terraform infrastructure are deployed and tested on AWS.

The repository contains the provider boundary required to swap the mock dependency for an open-weight STT → LLM → TTS implementation.

Actual GPU-based execution of faster-whisper/Llama/Mistral/Piper is not part of the current Fargate deployment.

The intended extension is:

```text
ALB
 |
 v
ECS Fargate
(API / Orchestrator)
 |
 v
Provider Interface
 |
 v
GPU Inference Tier
 |
 +-- faster-whisper STT
 |
 +-- Llama / Mistral LLM
 |
 +-- Piper TTS
```

This keeps the API/orchestration layer independently scalable from the GPU inference layer.

---

# Traffic Testing

Synthetic traffic can be generated using:

```bash
python scripts/generate_traffic.py \
  --base-url http://localhost:8000 \
  --duration-seconds 120 \
  --speed 60 \
  --start-hour 8
```

The traffic generator can be used to validate:

* Normal traffic
* Increased request rate
* Retry behavior
* Failure behavior
* Latency
* Circuit breaking
* DLQ behavior

Additional scripts:

```text
scripts/
├── generate_traffic.py
├── demo_failure.py
├── latency_test.py
├── inspect_dlq.py
└── replay_dlq.py
```

---

# Configuration

Configuration is provided through `.env`.

Important parameters include:

```text
MAX_ATTEMPTS
BACKOFF_BASE_MS
BACKOFF_MAX_MS
JITTER
CIRCUIT_FAILURE_THRESHOLD
CIRCUIT_RECOVERY_TIMEOUT
DOWNSTREAM_URL
DOWNSTREAM_FAILURE_RATE
```

The default downstream failure rate is configured around the challenge's 20% failure behavior.

Latency parameters are configurable and are calibrated around the challenge's target distribution.

---

# Testing

Run the complete test suite:

```bash
python -m pytest -q
```

The test suite covers:

* Retry behavior
* Exponential backoff
* Circuit breaker
* DLQ behavior
* AWS DLQ behavior
* Metrics
* Open-weight provider interface
* Mock service
* Traffic generation
* Processor behavior

Expected result for the current test suite:

```text
14 passed
```

---

# Repository Structure

```text
.
├── app/
│   ├── api/
│   │   └── main.py
│   │
│   ├── dlq/
│   │   └── repository.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── mock.py
│   │   └── open_weight.py
│   │
│   ├── services/
│   │   └── processor.py
│   │
│   ├── config.py
│   ├── models.py
│   ├── observability.py
│   └── resilience.py
│
├── scripts/
│   ├── generate_traffic.py
│   ├── demo_failure.py
│   ├── latency_test.py
│   ├── inspect_dlq.py
│   └── replay_dlq.py
│
├── tests/
│   ├── conftest.py
│   ├── test_resilience.py
│   ├── test_dlq.py
│   ├── test_aws_dlq.py
│   ├── test_observability.py
│   ├── test_open_weight.py
│   ├── test_mock_service.py
│   ├── test_traffic.py
│   └── test_processor.py
│
├── infra/
│   └── terraform/
│       ├── provider.tf
│       ├── variables.tf
│       ├── network.tf
│       ├── application.tf
│       ├── outputs.tf
│       └── GPU_OPTION.md
│
├── main.py
├── mock_service.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
├── RUNBOOK.md
├── COST_ANALYSIS.md
└── LICENSE
```

---

# Cost Analysis

AWS cost assumptions and deployment analysis are documented in:

```text
COST_ANALYSIS.md
```

The analysis covers:

* ECS Fargate
* Application Load Balancer
* NAT Gateway
* Supporting AWS infrastructure
* Baseline traffic
* Campaign spike traffic
* GPU extension considerations

Actual AWS charges should be verified through AWS Billing / Cost Explorer for the deployment window.

---

# Runbook

Operational procedures are documented in:

```text
RUNBOOK.md
```

The runbook covers:

* Deployment
* Health verification
* Traffic generation
* Failure injection
* Circuit-breaker validation
* DLQ inspection
* DLQ replay
* CloudWatch verification
* AWS teardown

---

# Teardown

Destroy the Terraform-managed infrastructure:

```powershell
terraform -chdir=infra/terraform destroy -auto-approve
```

After teardown, verify that billable resources have been removed.

For example:

```powershell
aws ecs list-clusters --region ap-south-1
```

Check NAT gateways:

```powershell
aws ec2 describe-nat-gateways `
  --region ap-south-1 `
  --filter Name=state,Values=available,pending `
  --output table
```

Check ECR repositories:

```powershell
aws ecr describe-repositories `
  --region ap-south-1 `
  --query "repositories[?contains(repositoryName, 'collections-challenge-demo')].repositoryName" `
  --output table
```

---

# Design Summary

The key design decision is to keep **resilience independent from inference implementation**.

```text
                    Inference Provider
                           |
                    Provider Interface
                           |
                 +---------+---------+
                 |                   |
            Mock Provider      Open-Weight Provider
                 |                   |
                 +---------+---------+
                           |
                    Resilience Layer
                    /              \
                 Retry        Circuit Breaker
                    \              /
                           |
                       Processor
                           |
                  +--------+--------+
                  |                 |
                 DLQ             Metrics
                  |                 |
             DynamoDB/SQS       CloudWatch
```

This allows the same production-oriented reliability layer to be used whether the downstream dependency is a mock service or an open-weight inference stack.

---

# License

This project is released under the **Apache License 2.0**.


