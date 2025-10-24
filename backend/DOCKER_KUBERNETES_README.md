# HelpChain Docker & Kubernetes Deployment

This guide provides instructions for deploying HelpChain using Docker and Kubernetes.

## 🏗️ Architecture Overview

HelpChain consists of the following components:

- **Flask Web Application**: Main application with analytics and ML capabilities
- **PostgreSQL Database**: Primary data storage
- **Redis**: Caching and Celery message broker
- **Celery Workers**: Background task processing
- **Nginx Ingress**: External access and load balancing

## 🚀 Quick Start with Docker Compose

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### Local Development Setup

1. **Clone the repository and navigate to backend:**

   ```bash
   cd backend
   ```

2. **Create environment file:**

   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Start all services:**

   ```bash
   docker-compose up -d
   ```

4. **Run database migrations:**

   ```bash
   docker-compose exec app flask db upgrade
   ```

5. **Access the application:**
   - Web App: http://localhost:5000
   - PgAdmin: http://localhost:5050 (admin@helpchain.local / admin123)
   - Redis Commander: http://localhost:8081

### Docker Compose Services

- `app`: Flask application with Gunicorn
- `db`: PostgreSQL 15 database
- `redis`: Redis 7 for caching and Celery
- `celery-worker`: Background task processing
- `celery-beat`: Celery scheduler
- `pgadmin`: Database management interface
- `redis-commander`: Redis management interface

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Docker registry access
- Storage class configured
- Ingress controller (nginx recommended)

### Environment Setup

1. **Configure your environment variables:**

   ```bash
   export DOCKER_REGISTRY=your-registry.com
   export IMAGE_TAG=v1.0.0
   ```

2. **Update Kubernetes secrets:**

   ```bash
   # Edit k8s/secret.yaml with your actual base64-encoded values
   # Generate base64: echo -n "your-value" | base64
   ```

3. **Update ConfigMap if needed:**
   ```bash
   # Edit k8s/configmap.yaml for your environment
   ```

### Deployment

1. **Make the deployment script executable:**

   ```bash
   chmod +x deploy.sh
   ```

2. **Run the deployment:**

   ```bash
   ./deploy.sh
   ```

   This will:
   - Build and push the Docker image
   - Create the namespace
   - Deploy all Kubernetes resources
   - Run database migrations
   - Show deployment status

### Manual Deployment

If you prefer manual deployment:

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Deploy configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml

# Deploy infrastructure
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# Wait for infrastructure
kubectl wait --for=condition=available --timeout=300s deployment/postgres -n helpchain
kubectl wait --for=condition=available --timeout=300s deployment/redis -n helpchain

# Deploy application
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/celery-worker.yaml
kubectl apply -f k8s/app-service.yaml

# Optional: Deploy ingress
kubectl apply -f k8s/ingress.yaml
```

### Database Migration

After deployment, run migrations:

```bash
# Get a pod name
POD_NAME=$(kubectl get pods -n helpchain -l app=helpchain,component=web -o jsonpath='{.items[0].metadata.name}')

# Run migrations
kubectl exec -n helpchain $POD_NAME -- flask db upgrade
```

## 🔧 Configuration

### Environment Variables

| Variable              | Description               | Default              |
| --------------------- | ------------------------- | -------------------- |
| `SECRET_KEY`          | Flask secret key          | Required             |
| `DATABASE_URL`        | PostgreSQL connection URL | Required             |
| `CELERY_BROKER_URL`   | Redis broker URL          | redis://redis:6379/0 |
| `MAIL_SERVER`         | SMTP server               | smtp.zoho.eu         |
| `MAIL_USERNAME`       | SMTP username             | Required             |
| `MAIL_PASSWORD`       | SMTP password             | Required             |
| `ADMIN_USER_PASSWORD` | Admin password            | Admin123             |

### Resource Requirements

| Component     | CPU Request | CPU Limit | Memory Request | Memory Limit |
| ------------- | ----------- | --------- | -------------- | ------------ |
| Web App       | 250m        | 500m      | 512Mi          | 1Gi          |
| PostgreSQL    | 250m        | 500m      | 256Mi          | 512Mi        |
| Redis         | 100m        | 200m      | 128Mi          | 256Mi        |
| Celery Worker | 100m        | 200m      | 256Mi          | 512Mi        |

## 📊 Monitoring & Maintenance

### Health Checks

- Web application: `/api` endpoint
- Database: Built-in PostgreSQL health checks
- Redis: Built-in Redis ping checks

### Logs

```bash
# View application logs
kubectl logs -n helpchain -l app=helpchain,component=web

# View database logs
kubectl logs -n helpchain -l app=helpchain,component=database

# View Celery worker logs
kubectl logs -n helpchain -l app=helpchain,component=celery-worker
```

### Scaling

```bash
# Scale web application
kubectl scale deployment helpchain-app -n helpchain --replicas=5

# Scale Celery workers
kubectl scale deployment celery-worker -n helpchain --replicas=3
```

### Backups

Set up regular backups for:

- PostgreSQL database
- Uploaded files (`/app/uploads`)
- ML models (`/app/models`)

## 🔒 Security Considerations

1. **Change default passwords** in production
2. **Use strong SECRET_KEY**
3. **Configure SSL/TLS** for all external traffic
4. **Restrict database access** to application pods only
5. **Regular security updates** for all components
6. **Network policies** for pod-to-pod communication

## 🐛 Troubleshooting

### Common Issues

1. **Pods not starting:**

   ```bash
   kubectl describe pod <pod-name> -n helpchain
   kubectl logs <pod-name> -n helpchain
   ```

2. **Database connection issues:**
   - Check PostgreSQL pod status
   - Verify DATABASE_URL configuration
   - Check network policies

3. **ML model loading issues:**
   - Ensure models volume is mounted
   - Check file permissions
   - Verify model files exist

### Useful Commands

```bash
# Get all resources
kubectl get all -n helpchain

# Check pod status
kubectl get pods -n helpchain

# Debug a pod
kubectl exec -it <pod-name> -n helpchain -- /bin/bash

# View events
kubectl get events -n helpchain --sort-by=.metadata.creationTimestamp

# Check resource usage
kubectl top pods -n helpchain
```

## 📚 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Flask Deployment](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [Gunicorn Documentation](https://docs.gunicorn.org/en/stable/)

## 🤝 Contributing

When making changes to the deployment:

1. Update this README if needed
2. Test locally with Docker Compose
3. Test on a staging Kubernetes cluster
4. Update resource limits if required
5. Document any new environment variables

---

For questions or issues, please create an issue in the repository.
