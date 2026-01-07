#!/bin/bash
# Deploy script for Kubernetes

set -e

NAMESPACE="vss-blueprint"
# If you want to prepend a registry (e.g. registry.example.com), set DOCKER_REGISTRY
# Otherwise leave empty to use Docker Hub repository format: username/repo
REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_NAME="${IMAGE_NAME:-balamkumar/vss-chat-bridge}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "🚀 Starting Kubernetes deployment..."
echo "Namespace: $NAMESPACE"
echo "Image: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG"

# Create namespace
echo "📦 Creating namespace..."
kubectl apply -f k8s/namespace.yaml

# Create service account
echo "🔐 Creating service account..."
kubectl apply -f k8s/serviceaccount.yaml

# Create ConfigMap
echo "⚙️  Creating ConfigMap..."
kubectl apply -f k8s/configmap.yaml

# Create deployment
echo "📡 Creating Deployment with 2 replicas..."
kubectl apply -f k8s/deployment.yaml

# Compute full image reference and update deployment image
if [ -n "$REGISTRY" ]; then
    IMAGE_REF="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
else
    IMAGE_REF="$IMAGE_NAME:$IMAGE_TAG"
fi

echo "🔄 Setting deployment image to $IMAGE_REF"
# Use kubectl set image to ensure the deployment uses the intended image
kubectl set image deployment/vss-bridge -n $NAMESPACE vss-bridge=$IMAGE_REF --record || true

# Create service
echo "🌐 Creating Service..."
kubectl apply -f k8s/service.yaml

# Create HPA
echo "📊 Creating Horizontal Pod Autoscaler..."
kubectl apply -f k8s/hpa.yaml

# Create Network Policy
echo "🔒 Creating Network Policy..."
kubectl apply -f k8s/network-policy.yaml

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -n $NAMESPACE -l app=vss-bridge -f"
echo "  kubectl describe deployment vss-bridge -n $NAMESPACE"
echo "  kubectl port-forward -n $NAMESPACE svc/vss-bridge 5000:80"
echo ""
