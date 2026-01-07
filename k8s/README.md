# Kubernetes Deployment Guide

This directory contains all Kubernetes manifests and deployment scripts for the REST API service.

## Files Overview

| File | Purpose |
|------|---------|
| `namespace.yaml` | Creates dedicated namespace for the application |
| `serviceaccount.yaml` | Creates service account for pod identity |
| `configmap.yaml` | Stores environment variables and configuration |
| `deployment.yaml` | Main deployment with 2 replicas, health checks, and resource limits |
| `service.yaml` | Exposes deployment as ClusterIP service |
| `hpa.yaml` | Horizontal Pod Autoscaler (auto-scales 2-5 replicas based on CPU/Memory) |
| `network-policy.yaml` | Network security policies for pod communication |
| `pod-disruption-budget.yaml` | Ensures at least 1 pod available during disruptions |
| `deploy.sh` | Automated deployment script |
| `cleanup.sh` | Automated cleanup script |

## Prerequisites

- Kubernetes cluster (v1.24+)
- `kubectl` configured to access your cluster
- Docker image pushed to registry (see parent README for build/push commands)

## Quick Deploy

### Option 1: Automated Deployment (Recommended)

```bash
# Make scripts executable
chmod +x k8s/deploy.sh k8s/cleanup.sh

# Deploy with default settings
./k8s/deploy.sh

# Deploy with custom image
DOCKER_REGISTRY=your-registry \
IMAGE_NAME=api-service \
IMAGE_TAG=v1.0 \
./k8s/deploy.sh
```

### Option 2: Manual Deployment

```bash
# Create all resources
kubectl apply -f k8s/

# Or apply individual files
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/network-policy.yaml
kubectl apply -f k8s/pod-disruption-budget.yaml
```

## Verify Deployment

```bash
# Check namespace
kubectl get namespace api-service

# Check pods (should see 2 running)
kubectl get pods -n api-service
kubectl get pods -n api-service -o wide

# Check deployment
kubectl describe deployment api-service -n api-service

# Check service
kubectl get svc -n api-service

# Check HPA status
kubectl get hpa -n api-service
kubectl describe hpa api-service-hpa -n api-service

# View logs
kubectl logs -n api-service -l app=api-service -f
kubectl logs -n api-service deployment/api-service -f

# Check resource usage
kubectl top pods -n api-service
kubectl top nodes
```

## Access the API

### Local Port-Forward

```bash
# Forward port 5000 to your machine
kubectl port-forward -n api-service svc/api-service 5000:80

# Test
curl http://localhost:5000/api/health
curl http://localhost:5000/api/data
```

### From Inside Cluster

```bash
# Use service DNS
# http://api-service.api-service.svc.cluster.local

# Or within same namespace
# http://api-service

# Example from another pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://api-service.api-service.svc.cluster.local/api/health
```

### Using Ingress (Optional)

For external access, create an Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: api-service
spec:
  ingressClassName: nginx  # or your ingress controller
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

## Configuration

### Environment Variables (ConfigMap)

Edit `configmap.yaml` to change:
- `FLASK_ENV`: Development or production
- `FLASK_DEBUG`: Enable/disable debug mode
- `FLASK_HOST`: Server host
- `FLASK_PORT`: Server port

```bash
# Update ConfigMap
kubectl set env configmap/api-config -n api-service FLASK_ENV=production

# Pods will automatically get new values on restart
```

### Replicas and Scaling

```bash
# Manual scaling
kubectl scale deployment api-service -n api-service --replicas=3

# View HPA
kubectl get hpa -n api-service -w
```

### Update Deployment

```bash
# Update image
kubectl set image deployment/api-service -n api-service \
  api-service=your-registry/api-service:v1.1

# Check rollout status
kubectl rollout status deployment/api-service -n api-service

# View history
kubectl rollout history deployment/api-service -n api-service

# Rollback if needed
kubectl rollout undo deployment/api-service -n api-service
```

## Health Checks & Probes

The deployment includes:

- **Liveness Probe**: Checks if container should be restarted (every 30s)
- **Readiness Probe**: Checks if pod should receive traffic (every 10s)
- **Both use**: `/api/health` endpoint

View probe activity:
```bash
kubectl describe pod -n api-service -l app=api-service
```

## Resource Management

Current limits:
- **Requests**: 100m CPU, 128Mi Memory
- **Limits**: 500m CPU, 256Mi Memory

Adjust in `deployment.yaml` based on your needs.

## Auto-scaling (HPA)

Automatically scales between 2-5 replicas based on:
- CPU utilization > 70%
- Memory utilization > 80%

```bash
# Monitor HPA
kubectl get hpa -n api-service -w
```

## Pod Disruption Budget

Ensures at least 1 pod remains available during:
- Node maintenance
- Cluster upgrades
- Pod evictions

## Network Security

`network-policy.yaml` restricts:
- Ingress: Only to port 5000
- Egress: Only to DNS and pod-to-pod communication

## Cleanup

```bash
# Delete everything
./k8s/cleanup.sh

# Or manually
kubectl delete namespace api-service
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl describe pod -n api-service <pod-name>

# Check logs
kubectl logs -n api-service <pod-name>

# Check events
kubectl get events -n api-service --sort-by='.lastTimestamp'
```

### Image pull errors

```bash
# Ensure image is pushed to registry
docker push your-registry/api-service:latest

# Update deployment with correct image
kubectl set image deployment/api-service -n api-service \
  api-service=your-registry/api-service:latest --record
```

### Service not reachable

```bash
# Check service endpoints
kubectl get endpoints -n api-service api-service

# Check DNS
kubectl exec -n api-service <pod-name> -- nslookup api-service

# Check network policies
kubectl get networkpolicy -n api-service
```

## Production Checklist

- [ ] Update image registry in deployment
- [ ] Configure resource requests/limits based on testing
- [ ] Set appropriate replicas and HPA thresholds
- [ ] Configure Ingress for external access
- [ ] Set up monitoring and alerting
- [ ] Configure persistent storage if needed
- [ ] Review security policies
- [ ] Set up backup strategy
- [ ] Test disaster recovery
- [ ] Document runbooks
