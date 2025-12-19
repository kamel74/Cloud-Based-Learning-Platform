# =============================================================================
# Cloud-Based Learning Platform - Phase 1 Infrastructure
# =============================================================================

provider "aws" {
  region  = "us-east-1"
  profile = "default"
}

# =============================================================================
# IAM Role for EC2 Instances
# =============================================================================

resource "aws_iam_role" "ec2_role" {
  name = "LearningPlatform-EC2-Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = { Name = "LearningPlatform-EC2-Role" }
}

resource "aws_iam_role_policy_attachment" "ec2_s3_access" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ec2_ssm_access" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "LearningPlatform-EC2-Profile"
  role = aws_iam_role.ec2_role.name
}

# =============================================================================
# VPC & Network Foundation
# =============================================================================

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  instance_tenancy     = "default"

  tags = { Name = "LearningPlatform-VPC" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "LearningPlatform-Internet-Gateway" }
}

# =============================================================================
# Subnets
# =============================================================================

resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = { Name = "Public-Subnet-AZ1" }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true

  tags = { Name = "Public-Subnet-AZ2" }
}

resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "us-east-1a"

  tags = { Name = "Private-Subnet-AZ1" }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "us-east-1b"

  tags = { Name = "Private-Subnet-AZ2" }
}

# =============================================================================
# NAT Gateway
# =============================================================================

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "NAT-Gateway-EIP" }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_1.id
  tags          = { Name = "Main-NAT-Gateway" }
}

# =============================================================================
# Route Tables
# =============================================================================

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "Public-Route-Table" }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = { Name = "Private-Route-Table" }
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# =============================================================================
# Security Groups
# =============================================================================

# ALB Security Group - Public facing
resource "aws_security_group" "alb" {
  name        = "ALB-Security-Group"
  vpc_id      = aws_vpc.main.id
  description = "Security group for Application Load Balancer"

  ingress {
    description = "HTTP from Internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from Internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "ALB-Security-Group" }
}

# Backend Nodes Security Group
resource "aws_security_group" "backend" {
  name        = "Backend-Nodes-Security-Group"
  vpc_id      = aws_vpc.main.id
  description = "Security group for backend application nodes"

  # SSH from VPC
  ingress {
    description = "SSH from VPC"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  # Application ports from ALB
  ingress {
    description     = "App traffic from ALB"
    from_port       = 5000
    to_port         = 5001
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Internal communication
  ingress {
    description = "Internal communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "Backend-Nodes-Security-Group" }
}

# Bastion Host Security Group
resource "aws_security_group" "bastion" {
  name        = "Bastion-Host-Security-Group"
  vpc_id      = aws_vpc.main.id
  description = "Security group for Bastion Host"

  ingress {
    description = "SSH from Internet"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "Bastion-Host-Security-Group" }
}

# Database Security Group
resource "aws_security_group" "database" {
  name        = "Database-Security-Group"
  description = "Allow PostgreSQL access from backend nodes"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from Backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "Database-Security-Group" }
}

# Lambda Security Group
resource "aws_security_group" "lambda" {
  name        = "Lambda-Security-Group"
  vpc_id      = aws_vpc.main.id
  description = "Security group for Lambda functions"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "Lambda-Security-Group" }
}

# =============================================================================
# S3 Buckets - Storage Layer
# =============================================================================

resource "random_string" "bucket_suffix" {
  length  = 6
  special = false
  upper   = false
}

locals {
  buckets = {
    tts       = "tts-service-storage"
    stt       = "stt-service-storage"
    chat      = "chat-service-storage"
    documents = "document-reader-storage"
    quiz      = "quiz-service-storage"
    shared    = "shared-assets-storage"
  }
}

resource "aws_s3_bucket" "services" {
  for_each      = local.buckets
  bucket        = "${each.value}-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = {
    Name    = each.value
    Service = each.key
  }
}

resource "aws_s3_bucket_public_access_block" "services" {
  for_each = aws_s3_bucket.services
  bucket   = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket for Lambda code
resource "aws_s3_bucket" "lambda_code" {
  bucket        = "lambda-functions-code-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = { Name = "Lambda-Functions-Code-Bucket" }
}

# =============================================================================
# RDS Databases - One per Service
# =============================================================================

resource "aws_db_subnet_group" "main" {
  name = "learning-platform-db-subnet-group"
  subnet_ids = [
    aws_subnet.private_1.id,
    aws_subnet.private_2.id
  ]

  tags = { Name = "LearningPlatform-DB-Subnet-Group" }
}

# Single RDS Instance with multiple databases inside
resource "aws_db_instance" "main" {
  identifier             = "learning-platform-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp2"
  db_name                = "learningplatform"
  username               = "dbadmin"
  password               = "SecurePassword123!" # Use Secrets Manager in production
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  tags = { Name = "LearningPlatform-Database" }
}

# =============================================================================
# SSH Key Pair
# =============================================================================

resource "tls_private_key" "main" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_key_pair" "main" {
  key_name   = "learning-platform-key"
  public_key = tls_private_key.main.public_key_openssh
}

resource "local_file" "ssh_key" {
  filename        = "learning-platform-key.pem"
  content         = tls_private_key.main.private_key_pem
  file_permission = "0400"
}

# =============================================================================
# EC2 Instances - Backend Nodes (without Kafka for Phase 1)
# =============================================================================

resource "aws_instance" "backend_nodes" {
  count                = 3
  ami                  = "ami-0e2c8caa4b6378d8c" # Ubuntu 24.04
  instance_type        = "t3.micro"
  subnet_id            = aws_subnet.private_1.id
  key_name             = aws_key_pair.main.key_name
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.backend.id]
  private_ip           = "10.0.10.${10 + count.index}"

  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io docker-compose python3-pip
              systemctl enable docker
              systemctl start docker
              usermod -aG docker ubuntu
              EOF

  tags = { Name = "Backend-Node-${count.index + 1}" }
}

# Bastion Host
resource "aws_instance" "bastion" {
  ami                    = "ami-0e2c8caa4b6378d8c" # Ubuntu 24.04
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_1.id
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.bastion.id]

  tags = { Name = "Bastion-Host" }
}

# =============================================================================
# Application Load Balancer (ALB) - Public Facing
# =============================================================================

resource "aws_lb" "api" {
  name               = "API-Load-Balancer"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = { Name = "API-Application-Load-Balancer" }
}

# Target Groups for each service
resource "aws_lb_target_group" "tts" {
  name     = "TTS-Service-TG"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = { Name = "TTS-Service-Target-Group" }
}

resource "aws_lb_target_group" "stt" {
  name     = "STT-Service-TG"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = { Name = "STT-Service-Target-Group" }
}

resource "aws_lb_target_group" "chat" {
  name     = "Chat-Service-TG"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = { Name = "Chat-Service-Target-Group" }
}

resource "aws_lb_target_group" "documents" {
  name     = "Documents-Service-TG"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = { Name = "Documents-Service-Target-Group" }
}

resource "aws_lb_target_group" "quiz" {
  name     = "Quiz-Service-TG"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = { Name = "Quiz-Service-Target-Group" }
}

# ALB Listener
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Learning Platform API is Live!"
      status_code  = "200"
    }
  }
}

# Listener Rules for routing
resource "aws_lb_listener_rule" "tts" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.tts.arn
  }

  condition {
    path_pattern {
      values = ["/api/tts/*"]
    }
  }
}

resource "aws_lb_listener_rule" "stt" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.stt.arn
  }

  condition {
    path_pattern {
      values = ["/api/stt/*"]
    }
  }
}

resource "aws_lb_listener_rule" "chat" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 30

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.chat.arn
  }

  condition {
    path_pattern {
      values = ["/api/chat/*"]
    }
  }
}

resource "aws_lb_listener_rule" "documents" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 40

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.documents.arn
  }

  condition {
    path_pattern {
      values = ["/api/documents/*"]
    }
  }
}

resource "aws_lb_listener_rule" "quiz" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 50

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.quiz.arn
  }

  condition {
    path_pattern {
      values = ["/api/quiz/*"]
    }
  }
}

# =============================================================================
# Lambda Functions - IAM Role
# =============================================================================

resource "aws_iam_role" "lambda_role" {
  name = "LearningPlatform-Lambda-Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = { Name = "LearningPlatform-Lambda-Role" }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# =============================================================================
# Lambda Function 1: S3 Document Upload Processor
# =============================================================================

data "archive_file" "s3_processor" {
  type        = "zip"
  output_path = "${path.module}/lambda_s3_processor.zip"

  source {
    content  = <<EOF
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Process S3 upload events - triggers when documents are uploaded"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        logger.info(f"Processing uploaded file: s3://{bucket}/{key}")
        
        # Add your document processing logic here
        # e.g., extract text, trigger other services
        
    return {
        'statusCode': 200,
        'body': json.dumps('Document processed successfully')
    }
EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "s3_processor" {
  filename         = data.archive_file.s3_processor.output_path
  function_name    = "S3-Document-Upload-Processor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  source_code_hash = data.archive_file.s3_processor.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = { Name = "S3-Document-Upload-Processor" }
}

# S3 trigger for document uploads
resource "aws_lambda_permission" "s3_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.s3_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.services["documents"].arn
}

resource "aws_s3_bucket_notification" "document_upload" {
  bucket = aws_s3_bucket.services["documents"].id

  lambda_function {
    lambda_function_arn = aws_lambda_function.s3_processor.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.s3_trigger]
}

# =============================================================================
# Lambda Function 2: Cleanup Old Files
# =============================================================================

data "archive_file" "cleanup" {
  type        = "zip"
  output_path = "${path.module}/lambda_cleanup.zip"

  source {
    content  = <<EOF
import json
import boto3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')

def lambda_handler(event, context):
    """Clean up old files from S3 buckets - runs on schedule"""
    logger.info("Starting cleanup task")
    
    # Define retention period (default 30 days)
    retention_days = int(event.get('retention_days', 30))
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    # List of buckets to clean (from environment or event)
    buckets_to_clean = event.get('buckets', [])
    
    deleted_count = 0
    for bucket in buckets_to_clean:
        try:
            response = s3.list_objects_v2(Bucket=bucket)
            for obj in response.get('Contents', []):
                if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                    s3.delete_object(Bucket=bucket, Key=obj['Key'])
                    deleted_count += 1
                    logger.info(f"Deleted: s3://{bucket}/{obj['Key']}")
        except Exception as e:
            logger.error(f"Error processing bucket {bucket}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Cleanup complete. Deleted {deleted_count} files.')
    }
EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "cleanup" {
  filename         = data.archive_file.cleanup.output_path
  function_name    = "Storage-Cleanup-Task"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  source_code_hash = data.archive_file.cleanup.output_base64sha256
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 256

  tags = { Name = "Storage-Cleanup-Task" }
}

# CloudWatch Event for scheduled cleanup (daily)
resource "aws_cloudwatch_event_rule" "cleanup_schedule" {
  name                = "Daily-Storage-Cleanup"
  description         = "Triggers cleanup Lambda daily"
  schedule_expression = "rate(1 day)"

  tags = { Name = "Daily-Storage-Cleanup-Rule" }
}

resource "aws_cloudwatch_event_target" "cleanup_target" {
  rule      = aws_cloudwatch_event_rule.cleanup_schedule.name
  target_id = "CleanupLambda"
  arn       = aws_lambda_function.cleanup.arn

  input = jsonencode({
    retention_days = 30
    buckets        = [for b in aws_s3_bucket.services : b.id]
  })
}

resource "aws_lambda_permission" "cleanup_cloudwatch" {
  statement_id  = "AllowCloudWatchInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cleanup_schedule.arn
}

# =============================================================================
# Lambda Function 3: Health Monitor
# =============================================================================

data "archive_file" "health_monitor" {
  type        = "zip"
  output_path = "${path.module}/lambda_health_monitor.zip"

  source {
    content  = <<EOF
import json
import boto3
import urllib.request
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    """Monitor health of backend services"""
    logger.info("Starting health check")
    
    services = event.get('services', [])
    results = {}
    
    for service in services:
        try:
            req = urllib.request.Request(service['url'], method='GET')
            req.add_header('Connection', 'close')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                results[service['name']] = 'healthy' if status == 200 else 'unhealthy'
        except Exception as e:
            results[service['name']] = 'unhealthy'
            logger.error(f"Health check failed for {service['name']}: {str(e)}")
        
        # Send metric to CloudWatch
        cloudwatch.put_metric_data(
            Namespace='LearningPlatform/Services',
            MetricData=[{
                'MetricName': 'ServiceHealth',
                'Dimensions': [{'Name': 'ServiceName', 'Value': service['name']}],
                'Value': 1 if results[service['name']] == 'healthy' else 0,
                'Unit': 'Count'
            }]
        )
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "health_monitor" {
  filename         = data.archive_file.health_monitor.output_path
  function_name    = "Service-Health-Monitor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  source_code_hash = data.archive_file.health_monitor.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = { Name = "Service-Health-Monitor" }
}

# CloudWatch Event for health checks (every 5 minutes)
resource "aws_cloudwatch_event_rule" "health_check_schedule" {
  name                = "Service-Health-Check"
  description         = "Triggers health monitor every 5 minutes"
  schedule_expression = "rate(5 minutes)"

  tags = { Name = "Service-Health-Check-Rule" }
}

resource "aws_cloudwatch_event_target" "health_check_target" {
  rule      = aws_cloudwatch_event_rule.health_check_schedule.name
  target_id = "HealthMonitorLambda"
  arn       = aws_lambda_function.health_monitor.arn
}

resource "aws_lambda_permission" "health_monitor_cloudwatch" {
  statement_id  = "AllowCloudWatchInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_check_schedule.arn
}

# =============================================================================
# Lambda Function 4: Auto Scaling Decision Maker
# =============================================================================

data "archive_file" "scaling_decision" {
  type        = "zip"
  output_path = "${path.module}/lambda_scaling.zip"

  source {
    content  = <<EOF
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    """Make scaling decisions based on CloudWatch metrics"""
    logger.info("Evaluating scaling decisions")
    
    # Get CPU utilization metrics
    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[],
        StartTime=event.get('start_time'),
        EndTime=event.get('end_time'),
        Period=300,
        Statistics=['Average']
    )
    
    avg_cpu = 0
    if response['Datapoints']:
        avg_cpu = sum(d['Average'] for d in response['Datapoints']) / len(response['Datapoints'])
    
    decision = {
        'average_cpu': avg_cpu,
        'recommendation': 'none'
    }
    
    # Scaling thresholds
    if avg_cpu > 80:
        decision['recommendation'] = 'scale_up'
        logger.info("High CPU detected - recommending scale up")
    elif avg_cpu < 20:
        decision['recommendation'] = 'scale_down'
        logger.info("Low CPU detected - recommending scale down")
    
    return {
        'statusCode': 200,
        'body': json.dumps(decision)
    }
EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "scaling_decision" {
  filename         = data.archive_file.scaling_decision.output_path
  function_name    = "AutoScaling-Decision-Maker"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  source_code_hash = data.archive_file.scaling_decision.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256

  tags = { Name = "AutoScaling-Decision-Maker" }
}

# =============================================================================
# Outputs
# =============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS Name"
  value       = aws_lb.api.dns_name
}

output "alb_url" {
  description = "Application Load Balancer URL"
  value       = "http://${aws_lb.api.dns_name}"
}

output "bastion_public_ip" {
  description = "Bastion Host Public IP"
  value       = aws_instance.bastion.public_ip
}

output "ssh_command" {
  description = "SSH command to connect to Bastion"
  value       = "ssh -i learning-platform-key.pem ubuntu@${aws_instance.bastion.public_ip}"
}

output "backend_node_ips" {
  description = "Private IPs of Backend Nodes"
  value       = aws_instance.backend_nodes[*].private_ip
}

output "rds_endpoint" {
  description = "RDS Database Endpoint"
  value       = aws_db_instance.main.address
}

output "rds_connection_info" {
  description = "RDS Connection Information"
  value = {
    endpoint = aws_db_instance.main.address
    port     = 5432
    database = "learningplatform"
    username = "dbadmin"
  }
}

output "s3_buckets" {
  description = "S3 Bucket Names"
  value = {
    for k, v in aws_s3_bucket.services : k => v.id
  }
}

output "lambda_functions" {
  description = "Lambda Function Names"
  value = {
    s3_processor    = aws_lambda_function.s3_processor.function_name
    cleanup         = aws_lambda_function.cleanup.function_name
    health_monitor  = aws_lambda_function.health_monitor.function_name
    scaling_decision = aws_lambda_function.scaling_decision.function_name
  }
}
