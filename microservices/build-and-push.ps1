# Build and Push Microservices to ECR (PowerShell)

$ErrorActionPreference = "Stop"

# Configuration
$AWS_REGION = "us-east-1"
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REGISTRY = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Login to ECR
Write-Host "Logging in to ECR..." -ForegroundColor Cyan
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Services to build
$SERVICES = @("tts-service", "stt-service", "chat-service", "document-reader-service", "quiz-service")

foreach ($SERVICE in $SERVICES) {
    Write-Host "`nBuilding $SERVICE..." -ForegroundColor Green
    Push-Location $SERVICE
    
    # Build image
    docker build -t "learning-platform/${SERVICE}:latest" .
    
    # Tag for ECR
    docker tag "learning-platform/${SERVICE}:latest" "$ECR_REGISTRY/learning-platform/${SERVICE}:latest"
    
    # Push to ECR
    Write-Host "Pushing $SERVICE to ECR..." -ForegroundColor Yellow
    docker push "$ECR_REGISTRY/learning-platform/${SERVICE}:latest"
    
    Pop-Location
    Write-Host "$SERVICE pushed successfully!" -ForegroundColor Green
}

Write-Host "`nAll services built and pushed to ECR!" -ForegroundColor Cyan
