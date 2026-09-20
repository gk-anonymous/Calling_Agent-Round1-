# Round 2 AWS Deployment Summary

## Result

Deployment completed successfully in `ap-south-1` using ECS Fargate.

## Deployed Resources

- ECR repositories for inference and mock containers
- VPC with public/private subnets, route tables, internet gateway, and one NAT Gateway
- ECS Fargate cluster, task definition, and service
- Internet-facing application load balancer
- DynamoDB and SQS DLQ resources
- IAM execution/task roles and policies
- CloudWatch log group, dashboard, and ECS autoscaling policy

## Endpoint

`http://collections-challenge-demo-722200242.ap-south-1.elb.amazonaws.com`

## Verification Evidence

- Terraform validation: passed
- Terraform plan: no changes pending
- ECS service: `ACTIVE`, 1 desired and 1 running task
- Health: `status=ok`, circuit state `CLOSED`
- ALB target health: `healthy`
- Terraform plan: no changes pending

## Cost Note

The stack includes billable NAT Gateway, ALB, and Fargate resources. Destroy the stack after review to stop ongoing charges.
