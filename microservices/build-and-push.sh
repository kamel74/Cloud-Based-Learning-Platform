#!/bin/bash
# Build and Push Microservices to ECR

set -e

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Services to build
SERVICES=("tts-service" "stt-service" "chat-service" "document-reader-service" "quiz-service")

for SERVICE in "${SERVICES[@]}"; do
    echo "Building $SERVICE..."
    cd $SERVICE
    
    # Build image
    docker build -t learning-platform/$SERVICE:latest .
    
    # Tag for ECR
    docker tag learning-platform/$SERVICE:latest $ECR_REGISTRY/learning-platform/$SERVICE:latest
    
    # Push to ECR
    echo "Pushing $SERVICE to ECR..."
    docker push $ECR_REGISTRY/learning-platform/$SERVICE:latest
    
    cd ..
    echo "$SERVICE pushed successfully!"
done

echo "All services built and pushed to ECR!"
