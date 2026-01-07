#!/bin/bash
# Cleanup script for Kubernetes

set -e

NAMESPACE="vss-blueprint"

echo "🗑️  Cleaning up Kubernetes resources..."

# Delete all resources in namespace
kubectl delete namespace $NAMESPACE --ignore-not-found=true

echo "✅ Cleanup completed!"
echo "Namespace '$NAMESPACE' and all resources deleted."
