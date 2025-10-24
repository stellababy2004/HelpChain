#!/bin/bash
# health-check.sh - Comprehensive Health Check Script for HelpChain

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_URL="${APP_URL:-http://localhost:5000}"
TIMEOUT=10
OUTPUT_FORMAT="${OUTPUT_FORMAT:-human}"  # human or json

# Health check results
declare -A results
overall_status="healthy"

# Function to check HTTP endpoint
check_http_endpoint() {
    local url="$1"
    local expected_status="${2:-200}"
    local name="$3"

    echo -e "${BLUE}🔍 Checking ${name}...${NC}"

    local response
    local http_code

    if response=$(curl -s -w "HTTPSTATUS:%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null); then
        http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

        if [[ "$http_code" == "$expected_status" ]]; then
            results["$name"]="healthy"
            echo -e "${GREEN}✅ ${name}: HTTP ${http_code}${NC}"
        else
            results["$name"]="unhealthy"
            overall_status="unhealthy"
            echo -e "${RED}❌ ${name}: HTTP ${http_code} (expected ${expected_status})${NC}"
        fi
    else
        results["$name"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ ${name}: Connection failed${NC}"
    fi
}

# Function to check database connectivity
check_database() {
    echo -e "${BLUE}📊 Checking database connectivity...${NC}"

    # Try to connect to database via application health endpoint
    if curl -s --max-time "$TIMEOUT" "${APP_URL}/health/database" >/dev/null 2>&1; then
        results["database"]="healthy"
        echo -e "${GREEN}✅ Database: Connected${NC}"
    else
        results["database"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ Database: Connection failed${NC}"
    fi
}

# Function to check Redis connectivity
check_redis() {
    echo -e "${BLUE}🔴 Checking Redis connectivity...${NC}"

    if curl -s --max-time "$TIMEOUT" "${APP_URL}/health/redis" >/dev/null 2>&1; then
        results["redis"]="healthy"
        echo -e "${GREEN}✅ Redis: Connected${NC}"
    else
        results["redis"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ Redis: Connection failed${NC}"
    fi
}

# Function to check Celery workers
check_celery() {
    echo -e "${BLUE}⚙️  Checking Celery workers...${NC}"

    if curl -s --max-time "$TIMEOUT" "${APP_URL}/health/celery" >/dev/null 2>&1; then
        results["celery"]="healthy"
        echo -e "${GREEN}✅ Celery: Workers active${NC}"
    else
        results["celery"]="warning"
        echo -e "${YELLOW}⚠️  Celery: Workers status unknown${NC}"
    fi
}

# Function to check disk space
check_disk_space() {
    echo -e "${BLUE}💾 Checking disk space...${NC}"

    local disk_usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

    if [[ $disk_usage -lt 85 ]]; then
        results["disk_space"]="healthy"
        echo -e "${GREEN}✅ Disk space: ${disk_usage}% used${NC}"
    elif [[ $disk_usage -lt 95 ]]; then
        results["disk_space"]="warning"
        echo -e "${YELLOW}⚠️  Disk space: ${disk_usage}% used${NC}"
    else
        results["disk_space"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ Disk space: ${disk_usage}% used (critical)${NC}"
    fi
}

# Function to check memory usage
check_memory() {
    echo -e "${BLUE}🧠 Checking memory usage...${NC}"

    local mem_usage
    mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')

    if [[ $mem_usage -lt 85 ]]; then
        results["memory"]="healthy"
        echo -e "${GREEN}✅ Memory: ${mem_usage}% used${NC}"
    elif [[ $mem_usage -lt 95 ]]; then
        results["memory"]="warning"
        echo -e "${YELLOW}⚠️  Memory: ${mem_usage}% used${NC}"
    else
        results["memory"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ Memory: ${mem_usage}% used (critical)${NC}"
    fi
}

# Function to check application response time
check_response_time() {
    echo -e "${BLUE}⏱️  Checking response time...${NC}"

    local response_time
    response_time=$(curl -s -w "%{time_total}" --max-time "$TIMEOUT" "${APP_URL}/health" -o /dev/null)

    # Convert to milliseconds
    local response_ms
    response_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "0")

    if (( $(echo "$response_time < 2.0" | bc -l 2>/dev/null || echo "1") )); then
        results["response_time"]="healthy"
        echo -e "${GREEN}✅ Response time: ${response_ms}ms${NC}"
    elif (( $(echo "$response_time < 5.0" | bc -l 2>/dev/null || echo "1") )); then
        results["response_time"]="warning"
        echo -e "${YELLOW}⚠️  Response time: ${response_ms}ms${NC}"
    else
        results["response_time"]="unhealthy"
        overall_status="unhealthy"
        echo -e "${RED}❌ Response time: ${response_ms}ms (slow)${NC}"
    fi
}

# Function to check SSL certificate
check_ssl_certificate() {
    if [[ "$APP_URL" == https://* ]]; then
        echo -e "${BLUE}🔒 Checking SSL certificate...${NC}"

        local domain
        domain=$(echo "$APP_URL" | sed 's|https://||' | sed 's|/.*||')

        if command -v openssl >/dev/null 2>&1; then
            local expiry_days
            expiry_days=$(echo | openssl s_client -servername "$domain" -connect "${domain}:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null | grep notAfter | cut -d= -f2 | xargs -I {} date -d {} +%s)
            local current_date
            current_date=$(date +%s)
            local days_left=$(( (expiry_days - current_date) / 86400 ))

            if [[ $days_left -gt 30 ]]; then
                results["ssl_certificate"]="healthy"
                echo -e "${GREEN}✅ SSL certificate: Expires in ${days_left} days${NC}"
            elif [[ $days_left -gt 7 ]]; then
                results["ssl_certificate"]="warning"
                echo -e "${YELLOW}⚠️  SSL certificate: Expires in ${days_left} days${NC}"
            else
                results["ssl_certificate"]="unhealthy"
                overall_status="unhealthy"
                echo -e "${RED}❌ SSL certificate: Expires in ${days_left} days${NC}"
            fi
        else
            results["ssl_certificate"]="unknown"
            echo -e "${YELLOW}⚠️  SSL certificate: Cannot check (openssl not available)${NC}"
        fi
    fi
}

# Function to output results in JSON format
output_json() {
    local json_results="{"
    json_results+="\"overall_status\":\"$overall_status\","
    json_results+="\"timestamp\":\"$(date -Iseconds)\","
    json_results+="\"checks\":{"


    local first=true
    for check in "${!results[@]}"; do
        if [[ "$first" == false ]]; then
            json_results+=","
        fi
        json_results+="\"$check\":\"${results[$check]}\""
        first=false
    done

    json_results+="}}"
    echo "$json_results"
}

# Function to output results in human format
output_human() {
    echo ""
    echo -e "${BLUE}📊 Health Check Summary${NC}"
    echo "========================"
    echo -e "Timestamp: $(date)"
    echo -e "Overall Status: ${overall_status^^}"

    echo ""
    echo -e "${BLUE}Detailed Results:${NC}"
    for check in "${!results[@]}"; do
        case "${results[$check]}" in
            "healthy")
                echo -e "✅ $check: HEALTHY"
                ;;
            "warning")
                echo -e "⚠️  $check: WARNING"
                ;;
            "unhealthy")
                echo -e "❌ $check: UNHEALTHY"
                ;;
            "unknown")
                echo -e "❓ $check: UNKNOWN"
                ;;
        esac
    done
}

# Main health check function
main() {
    echo -e "${BLUE}🏥 Starting HelpChain health check${NC}"
    echo "=================================="

    # Perform all checks
    check_http_endpoint "${APP_URL}/health" 200 "Application Health"
    check_http_endpoint "${APP_URL}/api/status" 200 "API Status"
    check_database
    check_redis
    check_celery
    check_disk_space
    check_memory
    check_response_time
    check_ssl_certificate

    # Output results
    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        output_json
    else
        output_human
    fi

    # Exit with appropriate code
    if [[ "$overall_status" == "healthy" ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"
