# GPU Option for Round 2

This repository does not provision GPU resources by default. The current Terraform stack is a cost-conscious ECS Fargate deployment with a real-shaped mock provider. The challenge's full GPU track requires a separately approved GPU capacity path.

## Recommended option

- Region: `ap-south-1`
- Instance: EC2 `g5.xlarge` with NVIDIA A10G and 24 GB VRAM
- STT: `faster-whisper` large-v3-turbo
- LLM: quantized Mistral-7B-Instruct-v0.3 or Llama-3.1-8B-Instruct
- TTS: Piper for the lower-latency CPU-friendly option

Run the model gateway in a private subnet and expose it only to the ECS task security group. Store model artifacts in EBS or an approved private object-store path. Use an instance profile limited to model artifact reads and CloudWatch log/metric publication.

## Approval gates before provisioning

1. Confirm the evaluator requires an actual GPU run rather than a documented option.
2. Request at least 4 vCPUs for `Running On-Demand G and VT instances` in `ap-south-1`.
3. Confirm model licenses and the intended public Apache 2.0 publication scope.
4. Confirm the budget and a destroy timestamp.
5. Add the GPU module/stack only after those approvals; it is intentionally absent from the default apply.

## CPU fallback

Use faster-whisper small/base, llama.cpp with a quantized 7B model, and Piper. This is useful for local contract and integration tests, but it is not equivalent to the AWS GPU Track and should be presented as a fallback only.

## Teardown

Stop the instance, remove the instance profile and security group, delete temporary model storage, and verify that no running GPU instances, EBS volumes, elastic IPs, or load balancers remain.
