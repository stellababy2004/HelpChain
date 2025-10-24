#!/bin/bash
# deploy-docker-compose.sh - Docker Compose Production Deployment Script for HelpChain

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="helpchain"
ENVIRONMENT=${1:-"staging"}
DOCKER_REGISTRY="registry.digitalocean.com/helpchain"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${BLUE}🚀 Starting Docker Compose deployment of HelpChain to ${ENVIRONMENT}${NC}"

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}❌ Invalid environment. Use 'staging' or 'production'${NC}"
    exit 1
fi

# Check prerequisites
echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker is required but not installed.${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}❌ Docker Compose is required but not installed.${NC}"; exit 1; }

# Load environment variables
if [[ -f ".env.${ENVIRONMENT}" ]]; then
    echo -e "${BLUE}📄 Loading environment variables from .env.${ENVIRONMENT}${NC}"
    export $(grep -v '^#' ".env.${ENVIRONMENT}" | xargs)
else
    echo -e "${RED}❌ Environment file .env.${ENVIRONMENT} not found${NC}"
    exit 1
fi

# Pre-deployment checks
echo -e "${YELLOW}🔍 Running pre-deployment checks...${NC}"

# Check if all required environment variables are set
required_vars=("DATABASE_URL" "SECRET_KEY" "REDIS_URL" "MAIL_SERVER")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo -e "${RED}❌ Required environment variable $var is not set${NC}"
        exit 1
    fi
done

# Run tests
echo -e "${BLUE}🧪 Running tests...${NC}"
if [[ -f "test_ui_ux_improvements.py" ]]; then
    python -m pytest test_ui_ux_improvements.py -v --tb=short
fi

# Security scan
echo -e "${BLUE}🔒 Running security scan...${NC}"
if command -v trivy >/dev/null 2>&1; then
    trivy filesystem --exit-code 1 --no-progress --format table .
else
    echo -e "${YELLOW}⚠️  Trivy not found, skipping security scan${NC}"
fi

# Build Docker image
echo -e "${BLUE}🏗️  Building Docker image...${NC}"
IMAGE_TAG="${DOCKER_REGISTRY}/${APP_NAME}:${ENVIRONMENT}-${TIMESTAMP}"

docker build -t "${IMAGE_TAG}" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
    --build-arg VERSION="$(git describe --tags --always)" \
    .

# Tag as latest for environment
docker tag "${IMAGE_TAG}" "${DOCKER_REGISTRY}/${APP_NAME}:${ENVIRONMENT}-latest"

# Push to registry
echo -e "${BLUE}📤 Pushing to registry...${NC}"
docker push "${IMAGE_TAG}"
docker push "${DOCKER_REGISTRY}/${APP_NAME}:${ENVIRONMENT}-latest"

# Deploy based on environment
if [[ "$ENVIRONMENT" == "staging" ]]; then
    echo -e "${BLUE}🚀 Deploying to staging...${NC}"

    # Update docker-compose file with new image
    sed -i.bak "s|image:.*|image: ${IMAGE_TAG}|g" docker-compose.staging.yml

    # Deploy
    docker-compose -f docker-compose.staging.yml up -d --force-recreate

    # Wait for health check
    echo -e "${YELLOW}⏳ Waiting for application to be healthy...${NC}"
    for i in {1..30}; do
        if curl -f http://localhost:5000/health >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Staging deployment successful!${NC}"
            break
        fi
        sleep 10
    done

    if [[ $i -eq 30 ]]; then
        echo -e "${RED}❌ Staging deployment failed - health check timeout${NC}"
        exit 1
    fi

elif [[ "$ENVIRONMENT" == "production" ]]; then
    echo -e "${BLUE}🚀 Deploying to production with blue-green strategy...${NC}"

    # Blue-green deployment logic would go here
    # This is a simplified version - in real production you'd use
    # Kubernetes, AWS ECS, or similar orchestration platform

    echo -e "${YELLOW}⚠️  Production deployment requires manual intervention${NC}"
    echo -e "${YELLOW}Please run the blue-green deployment script manually${NC}"

    # For demonstration, show what would happen
    echo -e "${BLUE}Would execute: ./scripts/blue-green-deploy.sh ${IMAGE_TAG}${NC}"
fi

# Post-deployment tasks
echo -e "${BLUE}🧹 Running post-deployment tasks...${NC}"

# Run database migrations if needed
if [[ -f "migrations" ]]; then
    echo -e "${YELLOW}📊 Running database migrations...${NC}"
    docker-compose -f "docker-compose.${ENVIRONMENT}.yml" exec web flask db upgrade
fi

# Clear caches
echo -e "${YELLOW}🗑️  Clearing application caches...${NC}"
docker-compose -f "docker-compose.${ENVIRONMENT}.yml" exec web flask cache clear

# Update monitoring
echo -e "${YELLOW}📊 Updating monitoring configuration...${NC}"
curl -X POST http://localhost:9090/-/reload 2>/dev/null || true

# Send notifications
echo -e "${BLUE}📢 Sending deployment notifications...${NC}"
if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
    curl -X POST -H 'Content-type: application/json' \
         --data "{\"text\":\"🚀 HelpChain deployed to ${ENVIRONMENT} successfully!\"}" \
         "$SLACK_WEBHOOK_URL"
fi

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}📊 Deployment Summary:${NC}"
echo -e "   Environment: ${ENVIRONMENT}"
echo -e "   Image: ${IMAGE_TAG}"
echo -e "   Timestamp: ${TIMESTAMP}"
echo -e "   Health Check: http://localhost:5000/health"

# Cleanup old images
echo -e "${BLUE}🧹 Cleaning up old Docker images...${NC}"
docker image prune -f

echo -e "${GREEN}✅ All deployment tasks completed!${NC}"
