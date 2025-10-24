#!/bin/bash
# blue-green-deploy.sh - Blue-Green Deployment Script for HelpChain

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="helpchain"
DOCKER_REGISTRY="registry.digitalocean.com/helpchain"
NEW_IMAGE_TAG="$1"

if [[ -z "$NEW_IMAGE_TAG" ]]; then
    echo -e "${RED}❌ Usage: $0 <new-image-tag>${NC}"
    echo -e "${YELLOW}Example: $0 registry.digitalocean.com/helpchain:production-20231201_143000${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Starting blue-green deployment for HelpChain${NC}"
echo -e "${BLUE}New Image: ${NEW_IMAGE_TAG}${NC}"

# Determine current active environment
if docker-compose -f docker-compose.blue.yml ps | grep -q "Up"; then
    ACTIVE_ENV="blue"
    INACTIVE_ENV="green"
    ACTIVE_COMPOSE="docker-compose.blue.yml"
    INACTIVE_COMPOSE="docker-compose.green.yml"
elif docker-compose -f docker-compose.green.yml ps | grep -q "Up"; then
    ACTIVE_ENV="green"
    INACTIVE_ENV="blue"
    ACTIVE_COMPOSE="docker-compose.green.yml"
    INACTIVE_COMPOSE="docker-compose.blue.yml"
else
    echo -e "${YELLOW}⚠️  No active environment found. Starting with blue environment.${NC}"
    ACTIVE_ENV="none"
    INACTIVE_ENV="blue"
    ACTIVE_COMPOSE=""
    INACTIVE_COMPOSE="docker-compose.blue.yml"
fi

echo -e "${BLUE}📊 Deployment Status:${NC}"
echo -e "   Active Environment: ${ACTIVE_ENV}"
echo -e "   Deploying to: ${INACTIVE_ENV}"

# Pre-deployment health check
if [[ "$ACTIVE_ENV" != "none" ]]; then
    echo -e "${YELLOW}🔍 Checking active environment health...${NC}"
    if ! curl -f --max-time 10 http://localhost:5000/health >/dev/null 2>&1; then
        echo -e "${RED}❌ Active environment is not healthy. Aborting deployment.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Active environment is healthy${NC}"
fi

# Update inactive environment with new image
echo -e "${BLUE}🏗️  Preparing ${INACTIVE_ENV} environment...${NC}"

# Create or update the inactive compose file
cp docker-compose.prod.yml "${INACTIVE_COMPOSE}"

# Update the image in the inactive compose file
sed -i.bak "s|image:.*|image: ${NEW_IMAGE_TAG}|g" "${INACTIVE_COMPOSE}"

# Start the inactive environment
echo -e "${BLUE}🚀 Starting ${INACTIVE_ENV} environment...${NC}"
docker-compose -f "${INACTIVE_COMPOSE}" up -d

# Wait for inactive environment to be ready
echo -e "${YELLOW}⏳ Waiting for ${INACTIVE_ENV} environment to be ready...${NC}"
for i in {1..60}; do
    if curl -f --max-time 5 http://localhost:5001/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ${INACTIVE_ENV} environment is ready!${NC}"
        break
    fi
    echo -e "${YELLOW}   Attempt $i/60 - waiting...${NC}"
    sleep 5
done

if [[ $i -eq 60 ]]; then
    echo -e "${RED}❌ ${INACTIVE_ENV} environment failed to become ready${NC}"
    echo -e "${YELLOW}🔄 Rolling back...${NC}"
    docker-compose -f "${INACTIVE_COMPOSE}" down
    exit 1
fi

# Run smoke tests on inactive environment
echo -e "${BLUE}🧪 Running smoke tests on ${INACTIVE_ENV} environment...${NC}"
if ! curl -f http://localhost:5001/api/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Smoke tests failed on ${INACTIVE_ENV} environment${NC}"
    echo -e "${YELLOW}🔄 Rolling back...${NC}"
    docker-compose -f "${INACTIVE_COMPOSE}" down
    exit 1
fi

# Run database migrations on inactive environment
echo -e "${BLUE}📊 Running database migrations on ${INACTIVE_ENV} environment...${NC}"
docker-compose -f "${INACTIVE_COMPOSE}" exec -T web flask db upgrade

# Switch traffic to inactive environment
echo -e "${BLUE}🔄 Switching traffic to ${INACTIVE_ENV} environment...${NC}"

# Update nginx configuration to point to new environment
# This assumes nginx is configured with upstream servers for blue/green
if [[ "$INACTIVE_ENV" == "blue" ]]; then
    sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-blue:5000; }/' /etc/nginx/sites-available/helpchain
else
    sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-green:5000; }/' /etc/nginx/sites-available/helpchain
fi

# Reload nginx configuration
nginx -t && nginx -s reload

# Wait for traffic to switch
echo -e "${YELLOW}⏳ Waiting for traffic to switch...${NC}"
sleep 10

# Verify new environment is handling traffic
echo -e "${BLUE}🔍 Verifying traffic switch...${NC}"
if ! curl -f --max-time 5 http://localhost/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Traffic switch failed - new environment not responding${NC}"
    echo -e "${YELLOW}🔄 Rolling back to ${ACTIVE_ENV}...${NC}"

    # Rollback nginx
    if [[ "$ACTIVE_ENV" == "blue" ]]; then
        sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-blue:5000; }/' /etc/nginx/sites-available/helpchain
    elif [[ "$ACTIVE_ENV" == "green" ]]; then
        sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-green:5000; }/' /etc/nginx/sites-available/helpchain
    fi
    nginx -s reload

    # Shutdown inactive environment
    docker-compose -f "${INACTIVE_COMPOSE}" down
    exit 1
fi

# Monitor for errors in the first few minutes
echo -e "${BLUE}📊 Monitoring for errors in first 2 minutes...${NC}"
ERROR_COUNT=0
for i in {1..24}; do
    if ! curl -f --max-time 5 http://localhost/health >/dev/null 2>&1; then
        ((ERROR_COUNT++))
        if [[ $ERROR_COUNT -gt 3 ]]; then
            echo -e "${RED}❌ Too many errors detected. Rolling back...${NC}"

            # Rollback nginx
            if [[ "$ACTIVE_ENV" == "blue" ]]; then
                sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-blue:5000; }/' /etc/nginx/sites-available/helpchain
            elif [[ "$ACTIVE_ENV" == "green" ]]; then
                sed -i 's/upstream helpchain_backend { server web-green:5000; }/' /etc/nginx/sites-available/helpchain
            fi
            nginx -s reload

            # Shutdown inactive environment
            docker-compose -f "${INACTIVE_COMPOSE}" down
            exit 1
        fi
    fi
    sleep 5
done

# Deployment successful - cleanup old environment
if [[ "$ACTIVE_ENV" != "none" ]]; then
    echo -e "${BLUE}🧹 Cleaning up old ${ACTIVE_ENV} environment...${NC}"
    docker-compose -f "${ACTIVE_COMPOSE}" down
fi

# Update deployment status
echo -e "${GREEN}✅ Blue-green deployment completed successfully!${NC}"
echo -e "${BLUE}📊 Deployment Summary:${NC}"
echo -e "   Previous Active: ${ACTIVE_ENV}"
echo -e "   New Active: ${INACTIVE_ENV}"
echo -e "   Image: ${NEW_IMAGE_TAG}"
echo -e "   Traffic switched successfully"

# Send success notification
if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
    curl -X POST -H 'Content-type: application/json' \
         --data "{\"text\":\"✅ HelpChain blue-green deployment successful! Active environment: ${INACTIVE_ENV}\"}" \
         "$SLACK_WEBHOOK_URL"
fi

# Optional: Keep old environment for quick rollback (configurable)
if [[ "${KEEP_OLD_ENV:-false}" == "true" ]]; then
    echo -e "${YELLOW}⚠️  Keeping old environment for quick rollback${NC}"
    echo -e "${YELLOW}To manually rollback: ./rollback.sh${NC}"
else
    echo -e "${BLUE}🧹 Removing old environment completely...${NC}"
    docker-compose -f "${ACTIVE_COMPOSE}" down -v 2>/dev/null || true
fi

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
