# Monitoring Stack

## Replace secrets

1. In `monitoring/prometheus/prometheus.yml`, replace:
`SUPER_LONG_RANDOM_TOKEN`

2. For Alertmanager Slack webhook:
copy `monitoring/.env.example` to `monitoring/.env` and set:
`SLACK_WEBHOOK_URL`

## Start

```powershell
cd monitoring
docker compose up -d
```

## Endpoints

- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`

## Reload (no restart)

```powershell
curl -X POST http://localhost:9090/-/reload
curl -X POST http://localhost:9093/-/reload
```
