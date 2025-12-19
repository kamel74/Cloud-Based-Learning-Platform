#!/bin/bash
# Blue-Green Deployment Script
# Usage: ./deploy.sh <image_tag>

set -e

IMAGE_TAG=${1:-latest}
ECR_REGISTRY="${ECR_REGISTRY:-233890242018.dkr.ecr.us-east-1.amazonaws.com}"
SERVICES=("tts-service" "stt-service" "chat-service" "document-reader-service" "quiz-service")

echo "🚀 Starting Blue-Green Deployment with tag: $IMAGE_TAG"

# Login to ECR
echo "📦 Logging into ECR..."
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Pull new images
echo "⬇️ Pulling new images..."
for service in "${SERVICES[@]}"; do
    echo "  Pulling $service:$IMAGE_TAG"
    docker pull $ECR_REGISTRY/learning-platform/$service:$IMAGE_TAG
    docker tag $ECR_REGISTRY/learning-platform/$service:$IMAGE_TAG \
               $ECR_REGISTRY/learning-platform/$service:latest
done

# Backup current deployment
echo "💾 Backing up current deployment..."
docker-compose ps > /tmp/deployment_backup.txt 2>/dev/null || true

# Deploy with docker-compose
echo "🔄 Deploying new containers..."
cd ~
docker-compose pull
docker-compose up -d --force-recreate

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Health check
echo "🏥 Running health checks..."
HEALTHY=true
PORTS=(5000 5001 5002 5003 5004)
SERVICE_NAMES=("tts" "stt" "chat" "documents" "quiz")

for i in "${!PORTS[@]}"; do
    port=${PORTS[$i]}
    name=${SERVICE_NAMES[$i]}
    if curl -sf http://localhost:$port/health > /dev/null 2>&1; then
        echo "  ✅ $name service (port $port) is healthy"
    else
        echo "  ❌ $name service (port $port) is unhealthy"
        HEALTHY=false
    fi
done

if [ "$HEALTHY" = true ]; then
    echo ""
    echo "🎉 Deployment successful!"
    echo "All services are running and healthy."
else
    echo ""
    echo "⚠️ Some services are unhealthy. Running rollback..."
    ./rollback.sh
    exit 1
fi
