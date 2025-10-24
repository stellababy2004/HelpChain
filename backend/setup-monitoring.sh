#!/bin/bash
# setup-monitoring.sh - Monitoring Stack Setup Script for HelpChain

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Setting up monitoring stack for HelpChain${NC}"

# Check prerequisites
echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker is required but not installed.${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}❌ Docker Compose is required but not installed.${NC}"; exit 1; }

# Create monitoring directories
echo -e "${BLUE}📁 Creating monitoring directories...${NC}"
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/alertmanager
mkdir -p monitoring/loki
mkdir -p monitoring/promtail

# Create Prometheus configuration
echo -e "${BLUE}⚙️  Creating Prometheus configuration...${NC}"
cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'helpchain-app'
    static_configs:
      - targets: ['web:5000']
    scrape_interval: 5s
    metrics_path: '/metrics'

  - job_name: 'helpchain-celery'
    static_configs:
      - targets: ['celery:5555']
    scrape_interval: 10s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    scrape_interval: 30s

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'loki'
    static_configs:
      - targets: ['loki:3100']
    scrape_interval: 15s
EOF

# Create alert rules
cat > monitoring/prometheus/alert_rules.yml << 'EOF'
groups:
  - name: helpchain_alerts
    rules:
      - alert: HelpChainDown
        expr: up{job="helpchain-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "HelpChain application is down"
          description: "HelpChain has been down for more than 1 minute."

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is above 2 seconds for 2 minutes."

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 5% for 2 minutes."

      - alert: DatabaseConnectionIssues
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection issues"
          description: "PostgreSQL is not responding."

      - alert: RedisConnectionIssues
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Redis connection issues"
          description: "Redis is not responding."

      - alert: DiskSpaceLow
        expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space"
          description: "Disk usage is above 85%."
EOF

# Create AlertManager configuration
echo -e "${BLUE}🚨 Creating AlertManager configuration...${NC}"
cat > monitoring/alertmanager/alertmanager.yml << 'EOF'
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@helpchain.com'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'email-notifications'
  routes:
  - match:
      severity: critical
    receiver: 'critical-notifications'

receivers:
- name: 'email-notifications'
  email_configs:
  - to: 'admin@helpchain.com'
    send_resolved: true

- name: 'critical-notifications'
  email_configs:
  - to: 'admin@helpchain.com,manager@helpchain.com'
    send_resolved: true
  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    channel: '#alerts'
    send_resolved: true
EOF

# Create Grafana datasource configuration
echo -e "${BLUE}📊 Creating Grafana datasource configuration...${NC}"
cat > monitoring/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
EOF

# Create Grafana dashboard configuration
cat > monitoring/grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'HelpChain Dashboards'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

# Create a basic HelpChain dashboard
cat > monitoring/grafana/dashboards/helpchain-overview.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "HelpChain Overview",
    "tags": ["helpchain"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Application Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "id": 2,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "Requests per second"
          }
        ]
      },
      {
        "id": 3,
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m]) * 100",
            "legendFormat": "Error rate %"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "timepicker": {},
    "templating": {
      "list": []
    },
    "annotations": {
      "list": []
    },
    "refresh": "5s",
    "schemaVersion": 16,
    "version": 0,
    "links": []
  }
}
EOF

# Create Loki configuration
echo -e "${BLUE}📝 Creating Loki configuration...${NC}"
cat > monitoring/loki/loki-config.yaml << 'EOF'
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
  - from: 2020-05-15
    store: boltdb-shipper
    object_store: filesystem
    schema: v11
    index:
      prefix: index_
      period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
EOF

# Create Promtail configuration
cat > monitoring/promtail/promtail-config.yaml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: helpchain-app
    static_configs:
      - targets:
          - localhost
        labels:
          job: helpchain-app
          __path__: /app/logs/*.log

  - job_name: nginx
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          __path__: /var/log/nginx/*.log
EOF

# Create docker-compose for monitoring
echo -e "${BLUE}🐳 Creating monitoring docker-compose file...${NC}"
cat > docker-compose.monitoring.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: helpchain-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/prometheus/alert_rules.yml:/etc/prometheus/alert_rules.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    networks:
      - monitoring
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: helpchain-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - monitoring
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: helpchain-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    networks:
      - monitoring
    restart: unless-stopped

  loki:
    image: grafana/loki:latest
    container_name: helpchain-loki
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki/loki-config.yaml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: helpchain-promtail
    volumes:
      - ./monitoring/promtail/promtail-config.yaml:/etc/promtail/config.yml
      - /app/logs:/app/logs
      - /var/log/nginx:/var/log/nginx
    command: -config.file=/etc/promtail/config.yml
    networks:
      - monitoring
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
  loki_data:

networks:
  monitoring:
    driver: bridge
EOF

# Start monitoring stack
echo -e "${BLUE}🚀 Starting monitoring stack...${NC}"
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for monitoring services to be ready...${NC}"
sleep 10

# Check service health
echo -e "${BLUE}🔍 Checking monitoring services...${NC}"

if curl -f http://localhost:9090/-/ready >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Prometheus is ready${NC}"
else
    echo -e "${RED}❌ Prometheus is not ready${NC}"
fi

if curl -f http://localhost:3000/api/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Grafana is ready${NC}"
else
    echo -e "${RED}❌ Grafana is not ready${NC}"
fi

if curl -f http://localhost:3100/ready >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Loki is ready${NC}"
else
    echo -e "${RED}❌ Loki is not ready${NC}"
fi

echo -e "${GREEN}🎉 Monitoring stack setup completed!${NC}"
echo -e "${BLUE}📊 Access URLs:${NC}"
echo -e "   Prometheus: http://localhost:9090"
echo -e "   Grafana: http://localhost:3000 (admin/admin)"
echo -e "   AlertManager: http://localhost:9093"
echo -e "   Loki: http://localhost:3100"
echo ""
echo -e "${YELLOW}⚠️  Important: Update the following configurations:${NC}"
echo -e "   1. AlertManager email settings in monitoring/alertmanager/alertmanager.yml"
echo -e "   2. Slack webhook URL in monitoring/alertmanager/alertmanager.yml"
echo -e "   3. Grafana admin password (currently set to 'admin')"
echo -e "   4. Adjust alert thresholds in monitoring/prometheus/alert_rules.yml"
