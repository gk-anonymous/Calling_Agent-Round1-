# Round 2 AWS Deployment Plan

## Scope

Deploy the existing FastAPI Round 2 demo from `d:/Calling_Agent` to AWS region `ap-south-1` using the Terraform configuration under `infra/terraform`.

## Deployment Type

- Provision and deploy a short-lived ECS Fargate demo stack.
- Terraform-managed resources: VPC, public/private subnets, one NAT Gateway, security groups, ECR repositories, ECS cluster/service/task definition, ALB, DynamoDB DLQ table, SQS DLQ queue, IAM roles, CloudWatch logs/dashboard, and ECS autoscaling.
- Container image: the repository Dockerfile, pushed to both Terraform-created ECR repositories. The ECS task runs the mock provider and FastAPI service as sidecars.

## Execution Steps

1. Confirm `aws sts get-caller-identity`, Docker, and Terraform are available and validate Terraform.
2. Initialize Terraform in `infra/terraform`.
3. Create only the two ECR repositories with a targeted Terraform apply.
4. Authenticate Docker to ECR, build the repository image, tag it for both repositories, and push both tags.
5. Apply the complete Terraform stack with `image_tag=latest`.
6. Read the ALB URL and verify `/health`.
7. Run the traffic generator for a short demo and inspect `/metrics` and the pending DLQ endpoint.
8. Capture the service URL, task/metric/log evidence, and Terraform outputs.
9. Destroy the stack immediately after evidence capture to stop billable NAT, ALB, and Fargate resources.

## Files In Scope

- Existing Terraform files under `infra/terraform/`
- Existing `Dockerfile`
- Existing `scripts/generate_traffic.py`
- Deployment tracking files under `.github/modernize/deployment/`

## Validation

- `terraform fmt -check`
- `terraform validate`
- AWS identity check
- Docker image push completion
- ECS/ALB health response
- Traffic, metrics, and DLQ endpoint responses
- Successful Terraform destroy

## Cost and Safety Constraints

This is a short-lived demo. NAT Gateway, ALB, Fargate, and related resources are billable and are not assumed to be covered by Free Tier. Do not deploy GPU resources. Do not store secrets in files. Do not destroy until evidence has been captured unless deployment fails and cleanup is required.
