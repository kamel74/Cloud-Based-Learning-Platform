#!/bin/bash
# Rollback Script
# Usage: ./rollback.sh

set -e

echo "🔄 Starting rollback..."

cd ~

# Stop current containers
echo "🛑 Stopping current containers..."
docker-compose down

# Try to restart with previous images
echo "▶️ Restarting previous deployment..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to restart..."
sleep 30

# Verify rollback
echo "🏥 Verifying rollback..."
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
    echo "✅ Rollback completed successfully!"
else
    echo ""
    echo "❌ Rollback failed! Manual intervention required."
    exit 1
fi
