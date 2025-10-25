#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Generate nginx.conf from template
envsubst '${PORT}' < nginx.conf.template > nginx.conf

echo "[OK] Configuration generated"
echo "[INFO] Starting services..."

# Start all services
docker compose up -d

echo "[INFO] Waiting for services to be healthy..."
sleep 10

echo "[OK] Services started!"
echo ""
echo "Endpoints:"
echo "   Main (Nginx):  http://localhost:${NGINX_PORT}"
echo "   Blue direct:   http://localhost:${BLUE_PORT}"
echo "   Green direct:  http://localhost:${GREEN_PORT}"
echo ""
echo "Test with: curl http://localhost:${NGINX_PORT}/version"
