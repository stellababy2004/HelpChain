#!/bin/bash

# HelpChain Kubernetes Deployment Script
# This script helps deploy HelpChain to a Kubernetes cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="helpchain"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-your-registry.com}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo -e "${BLUE}🚀 HelpChain Kubernetes Deployment${NC}"
echo "================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    if ! command_exists kubectl; then
        echo -e "${RED}❌ kubectl is not installed. Please install it first.${NC}"
        exit 1
    fi

    if ! command_exists docker; then
        echo -e "${RED}❌ docker is not installed. Please install it first.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Build and push Docker image
build_and_push_image() {
    echo -e "${YELLOW}Building and pushing Docker image...${NC}"

    # Build the image
    docker build -t ${DOCKER_REGISTRY}/helpchain:${IMAGE_TAG} .

    # Push the image
    docker push ${DOCKER_REGISTRY}/helpchain:${IMAGE_TAG}

    echo -e "${GREEN}✅ Docker image built and pushed${NC}"
}

# Deploy to Kubernetes
deploy_to_k8s() {
    echo -e "${YELLOW}Deploying to Kubernetes...${NC}"

    # Create namespace
    kubectl apply -f k8s/namespace.yaml

    # Apply configurations
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    kubectl apply -f k8s/pvc.yaml

    # Deploy infrastructure
    kubectl apply -f k8s/postgres.yaml
    kubectl apply -f k8s/redis.yaml

    # Wait for infrastructure to be ready
    echo "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/postgres -n ${NAMESPACE}

    echo "Waiting for Redis to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/redis -n ${NAMESPACE}

    # Update the image in the deployment
    sed -i "s|image: helpchain:latest|image: ${DOCKER_REGISTRY}/helpchain:${IMAGE_TAG}|g" k8s/app-deployment.yaml
    sed -i "s|image: helpchain:latest|image: ${DOCKER_REGISTRY}/helpchain:${IMAGE_TAG}|g" k8s/celery-worker.yaml

    # Deploy application
    kubectl apply -f k8s/app-deployment.yaml
    kubectl apply -f k8s/celery-worker.yaml
    kubectl apply -f k8s/app-service.yaml

    # Apply ingress (optional)
    read -p "Do you want to apply the ingress? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl apply -f k8s/ingress.yaml
    fi

    echo -e "${GREEN}✅ Deployment completed${NC}"
}

# Run database migrations
run_migrations() {
    echo -e "${YELLOW}Running database migrations...${NC}"

    # Get the first running pod
    POD_NAME=$(kubectl get pods -n ${NAMESPACE} -l app=helpchain,component=web -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$POD_NAME" ]; then
        echo -e "${RED}❌ No application pods found${NC}"
        exit 1
    fi

    # Run migrations
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- flask db upgrade

    echo -e "${GREEN}✅ Database migrations completed${NC}"
}

# Check deployment status
check_deployment() {
    echo -e "${YELLOW}Checking deployment status...${NC}"

    echo "Pods:"
    kubectl get pods -n ${NAMESPACE}

    echo -e "\nServices:"
    kubectl get services -n ${NAMESPACE}

    echo -e "\nIngress:"
    kubectl get ingress -n ${NAMESPACE}

    echo -e "\n${GREEN}✅ Deployment status checked${NC}"
}

# Main deployment flow
main() {
    check_prerequisites

    read -p "Do you want to build and push the Docker image? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_and_push_image
    fi

    deploy_to_k8s

    read -p "Do you want to run database migrations? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_migrations
    fi

    check_deployment

    echo -e "${GREEN}🎉 HelpChain deployment completed successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Update your DNS to point to the ingress IP"
    echo "2. Configure SSL certificates if needed"
    echo "3. Set up monitoring and logging"
    echo "4. Configure backups for the database"
}

# Run main function
main "$@"