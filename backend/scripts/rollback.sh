#!/bin/bash
# rollback.sh - Quick Rollback Script for HelpChain Blue-Green Deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Starting rollback procedure for HelpChain${NC}"

# Determine current active environment
if docker-compose -f docker-compose.blue.yml ps | grep -q "Up"; then
    CURRENT_ACTIVE="blue"
    ROLLBACK_TARGET="green"
elif docker-compose -f docker-compose.green.yml ps | grep -q "Up"; then
    CURRENT_ACTIVE="green"
    ROLLBACK_TARGET="blue"
else
    echo -e "${RED}❌ No active environment found. Cannot rollback.${NC}"
    exit 1
fi

echo -e "${BLUE}📊 Current Status:${NC}"
echo -e "   Currently Active: ${CURRENT_ACTIVE}"
echo -e "   Rolling back to: ${ROLLBACK_TARGET}"

# Check if rollback target is available
if ! docker-compose -f "docker-compose.${ROLLBACK_TARGET}.yml" ps | grep -q "Up"; then
    echo -e "${RED}❌ Rollback target (${ROLLBACK_TARGET}) is not available${NC}"
    exit 1
fi

# Check rollback target health
echo -e "${YELLOW}🔍 Checking ${ROLLBACK_TARGET} environment health...${NC}"
if ! curl -f --max-time 5 http://localhost:5001/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Rollback target is not healthy. Cannot rollback.${NC}"
    exit 1
fi

# Switch traffic back
echo -e "${BLUE}🔄 Switching traffic back to ${ROLLBACK_TARGET}...${NC}"

# Update nginx configuration
if [[ "$ROLLBACK_TARGET" == "blue" ]]; then
    sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-blue:5000; }/' /etc/nginx/sites-available/helpchain
else
    sed -i 's/upstream helpchain_backend {.*}/upstream helpchain_backend { server web-green:5000; }/' /etc/nginx/sites-available/helpchain
fi

# Reload nginx
nginx -t && nginx -s reload

# Wait for traffic switch
echo -e "${YELLOW}⏳ Waiting for traffic to switch...${NC}"
sleep 5

# Verify rollback successful
echo -e "${BLUE}🔍 Verifying rollback...${NC}"
if curl -f --max-time 5 http://localhost/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Rollback successful!${NC}"

    # Shutdown the failed environment
    echo -e "${BLUE}🧹 Shutting down failed ${CURRENT_ACTIVE} environment...${NC}"
    docker-compose -f "docker-compose.${CURRENT_ACTIVE}.yml" down

    # Send notification
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
             --data "{\"text\":\"🔄 HelpChain rolled back to ${ROLLBACK_TARGET} environment\"}" \
             "$SLACK_WEBHOOK_URL"
    fi

    echo -e "${GREEN}🎉 Rollback completed successfully!${NC}"
else
    echo -e "${RED}❌ Rollback verification failed${NC}"
    exit 1
fi