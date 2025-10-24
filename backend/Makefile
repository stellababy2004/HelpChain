# HelpChain Development Makefile

.PHONY: help build up down logs clean test deploy k8s-deploy k8s-logs k8s-status

# Default target
help:
	@echo "HelpChain Development Commands:"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - Show logs from all services"
	@echo "  make logs-app     - Show app logs only"
	@echo "  make shell        - Open shell in app container"
	@echo "  make test         - Run tests in container"
	@echo "  make clean        - Remove containers and volumes"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make k8s-deploy  - Deploy to Kubernetes"
	@echo "  make k8s-logs    - Show Kubernetes logs"
	@echo "  make k8s-status  - Show Kubernetes status"
	@echo "  make k8s-clean   - Clean Kubernetes deployment"
	@echo ""
	@echo "Database:"
	@echo "  make db-upgrade  - Run database migrations"
	@echo "  make db-shell    - Open database shell"
	@echo ""
	@echo "ML/Analytics:"
	@echo "  make train-models - Train ML models"
	@echo ""

# Docker Compose commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-app:
	docker-compose logs -f app

shell:
	docker-compose exec app /bin/bash

test:
	docker-compose exec app python -m pytest

clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

# Database commands
db-upgrade:
	docker-compose exec app flask db upgrade

db-shell:
	docker-compose exec db psql -U helpchain -d helpchain

# ML commands
train-models:
	docker-compose exec app python -c "from predictive_analytics import get_predictive_analytics; pa = get_predictive_analytics(); pa.train_models()"

# Kubernetes commands
k8s-deploy:
	./deploy.sh

k8s-logs:
	kubectl logs -n helpchain -l app=helpchain --tail=100 -f

k8s-status:
	kubectl get all -n helpchain

k8s-clean:
	kubectl delete namespace helpchain --ignore-not-found=true

# Development setup
setup: build up db-upgrade
	@echo "Development environment is ready!"
	@echo "Access the app at: http://localhost:5000"
	@echo "PgAdmin at: http://localhost:5050"
	@echo "Redis Commander at: http://localhost:8081"
