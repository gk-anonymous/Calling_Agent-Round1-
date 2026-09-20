resource "aws_ecr_repository" "inference" {
  name                 = "${local.name}-inference"
  force_delete         = true
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "mock" {
  name                 = "${local.name}-mock"
  force_delete         = true
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "service" {
  name              = "/ecs/${local.name}"
  retention_in_days = 7
}

resource "aws_sqs_queue" "dlq" {
  name                       = "${local.name}-dlq"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600
}

resource "aws_dynamodb_table" "dlq" {
  name         = "${local.name}-dlq"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "record_type"
  range_key    = "event_id"

  attribute {
    name = "record_type"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name = "${local.name}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "task" {
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Scan"]
        Resource = aws_dynamodb_table.dlq.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]
        Resource = aws_sqs_queue.dlq.arn
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "CollectionsChallenge" }
        }
      }
    ]
  })
}

resource "aws_ecs_task_definition" "service" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "mock"
      image     = "${aws_ecr_repository.mock.repository_url}:${var.image_tag}"
      essential = true
      command   = ["uvicorn", "mock_service:app", "--host", "0.0.0.0", "--port", "8001"]
      portMappings = [{
        containerPort = 8001
      }]
      environment = [{
        name  = "DOWNSTREAM_FAILURE_RATE"
        value = var.downstream_failure_rate
      }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "mock"
        }
      }
    },
    {
      name      = "inference"
      image     = "${aws_ecr_repository.inference.repository_url}:${var.image_tag}"
      essential = true
      dependsOn = [{
        containerName = "mock"
        condition     = "START"
      }]
      portMappings = [{
        containerPort = 8000
      }]
      environment = [
        { name = "DOWNSTREAM_URL", value = "http://127.0.0.1:8001" },
        { name = "DLQ_BACKEND", value = "aws" },
        { name = "AWS_DLQ_TABLE", value = aws_dynamodb_table.dlq.name },
        { name = "AWS_DLQ_QUEUE_URL", value = aws_sqs_queue.dlq.url },
        { name = "PUBLISH_CLOUDWATCH_METRICS", value = "true" },
        { name = "CLOUDWATCH_PUBLISH_INTERVAL_SECONDS", value = "10" },
        { name = "CLOUDWATCH_NAMESPACE", value = "CollectionsChallenge" },
        { name = "SERVICE_NAME", value = local.name }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "inference"
        }
      }
    }
  ])
}

resource "aws_lb" "main" {
  name               = substr(local.name, 0, 32)
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "service" {
  name        = substr("${local.name}-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.service.arn
  }
}

resource "aws_ecs_service" "service" {
  name            = local.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.service.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.service.arn
    container_name   = "inference"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_appautoscaling_target" "service" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "inflight" {
  name               = "${local.name}-inflight"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.service.resource_id
  scalable_dimension = aws_appautoscaling_target.service.scalable_dimension
  service_namespace  = aws_appautoscaling_target.service.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = var.inflight_calls_per_task
    scale_in_cooldown  = 30
    scale_out_cooldown = 30

    customized_metric_specification {
      metric_name = "InFlightCalls"
      namespace   = "CollectionsChallenge"
      statistic   = "Average"
      unit        = "Count"

      dimensions {
        name  = "Service"
        value = local.name
      }
    }
  }
}

resource "aws_cloudwatch_dashboard" "service" {
  dashboard_name = local.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "In-flight calls and task count"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["CollectionsChallenge", "InFlightCalls", "Service", local.name],
            ["AWS/ECS", "RunningTaskCount", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.service.name]
          ]
          stat   = "Average"
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Request outcomes and retries"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["CollectionsChallenge", "RequestsTotal", "Service", local.name],
            ["CollectionsChallenge", "RequestsSuccess", "Service", local.name],
            ["CollectionsChallenge", "RequestsFailed", "Service", local.name],
            ["CollectionsChallenge", "RetryTotal", "Service", local.name]
          ]
          stat   = "Sum"
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Latency percentiles"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["CollectionsChallenge", "latency_p50_ms", "Service", local.name],
            ["CollectionsChallenge", "latency_p90_ms", "Service", local.name],
            ["CollectionsChallenge", "latency_p95_ms", "Service", local.name],
            ["CollectionsChallenge", "latency_p99_ms", "Service", local.name]
          ]
          stat   = "Average"
          period = 60
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          query  = "SOURCE '${aws_cloudwatch_log_group.service.name}' | fields @timestamp, @message | sort @timestamp desc | limit 100"
          region = var.aws_region
          title  = "Recent service logs"
          view   = "table"
        }
      }
    ]
  })
}