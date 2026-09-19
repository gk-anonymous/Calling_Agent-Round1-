output "service_url" {
  value = "http://${aws_lb.main.dns_name}"
}

output "inference_ecr_repository" {
  value = aws_ecr_repository.inference.repository_url
}

output "mock_ecr_repository" {
  value = aws_ecr_repository.mock.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "service_name" {
  value = aws_ecs_service.service.name
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.service.dashboard_name
}

output "dlq_table" {
  value = aws_dynamodb_table.dlq.name
}

output "dlq_queue_url" {
  value = aws_sqs_queue.dlq.url
}