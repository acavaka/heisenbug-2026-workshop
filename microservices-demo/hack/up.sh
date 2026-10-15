#!/usr/bin/env bash
# Raise Kind cluster + Online Boutique. Usage: ./hack/up.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
MANIFEST="${ROOT}/release/kubernetes-manifests.yaml"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' not found in PATH" >&2
    exit 1
  }
}

need docker
need kind
need kubectl

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

if ! kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "==> Creating Kind cluster '${CLUSTER_NAME}'..."
  kind create cluster --name "${CLUSTER_NAME}"
else
  echo "==> Kind cluster '${CLUSTER_NAME}' already exists"
fi

kubectl config use-context "${CONTEXT}" >/dev/null

echo "==> Applying Online Boutique manifests..."
kubectl apply -f "${MANIFEST}"

echo "==> Scaling loadgenerator to 0 (no background traffic)..."
kubectl scale deployment/loadgenerator --replicas=0 2>/dev/null || true

echo "==> Waiting for core pods (this can take several minutes on first image pull)..."
kubectl wait --for=condition=available --timeout=600s \
  deployment/frontend \
  deployment/productcatalogservice \
  deployment/cartservice \
  deployment/checkoutservice \
  deployment/paymentservice \
  deployment/currencyservice \
  deployment/shippingservice \
  deployment/emailservice \
  deployment/recommendationservice \
  deployment/adservice \
  deployment/redis-cart \
  || true

echo
kubectl get pods
echo
echo "Done. Context: ${CONTEXT}"
echo "Next: ./hack/ports.sh   then open http://127.0.0.1:8080"
echo "Optional workshop image: ./hack/build-and-load-bug1024.sh"
