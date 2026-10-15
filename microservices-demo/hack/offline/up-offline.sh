#!/usr/bin/env bash
# Fully offline Kind bring-up: load local image tars, apply boutique/* manifests (Never).
# Prerequisites: Docker running; hack/offline/images/*.tar OR workshop-images.tar.gz present.
# No registry pulls (gcr.io / docker.io) required if images were prepared by export-images.sh.
set -euo pipefail

OFFLINE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${OFFLINE}/../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
GEN="${OFFLINE}/generated"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }; }
need docker
need kind
need kubectl
need python3

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running." >&2
  exit 1
fi

chmod +x "${OFFLINE}"/*.sh 2>/dev/null || true

echo "==> 1/4 Load images into Docker + Kind (offline)"
"${OFFLINE}/load-images.sh"

echo "==> 2/4 Generate offline manifests"
"${OFFLINE}/generate-manifests.sh"

kubectl config use-context "${CONTEXT}" >/dev/null

echo "==> 3/4 Apply Boutique (local images)"
kubectl apply -f "${GEN}/kubernetes-manifests-offline.yaml"
kubectl scale deployment/loadgenerator --replicas=0 2>/dev/null || true

echo "==> 4/4 Apply workshop stack (Tempo/Grafana/Prom/Postgres/Temporal/order-worker)"
kubectl apply -f "${GEN}/workshop/"

# Prefer BUG-1024 workshop images if loaded
if docker image inspect boutique/productcatalogservice:workshop-bug1024 >/dev/null 2>&1; then
  echo "==> Switching catalog/frontend to BUG-1024 workshop images"
  kubectl set image deployment/productcatalogservice "server=boutique/productcatalogservice:workshop-bug1024" || true
  kubectl set image deployment/frontend "server=boutique/frontend:workshop-bug1024" || true
  kubectl patch deployment productcatalogservice --type=json -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
  ]' 2>/dev/null || true
  kubectl patch deployment frontend --type=json -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
  ]' 2>/dev/null || true
  if [[ -f "${GEN}/workshop-bug1024-patch.yaml" ]]; then
    kubectl apply -f "${GEN}/workshop-bug1024-patch.yaml" || true
  fi
  kubectl set env deployment/productcatalogservice ADMIN_PORT=8081 PRICE_CACHE_TTL_SECONDS=3600 2>/dev/null || true
fi

# Enable tracing to local Tempo
for dep in frontend checkoutservice paymentservice productcatalogservice \
           currencyservice emailservice recommendationservice; do
  kubectl set env "deployment/${dep}" \
    ENABLE_TRACING=1 \
    COLLECTOR_SERVICE_ADDR=tempo:4317 \
    2>/dev/null || true
done

echo "==> Waiting for core deployments (may take a few minutes; no image pulls)..."
kubectl wait --for=condition=available --timeout=600s \
  deployment/frontend \
  deployment/productcatalogservice \
  deployment/cartservice \
  deployment/checkoutservice \
  deployment/paymentservice \
  deployment/postgres \
  deployment/tempo \
  deployment/grafana \
  deployment/temporal \
  || true

kubectl get pods
echo
echo "Done (offline). Context: ${CONTEXT}"
echo "Next: ./hack/workshop/ports-workshop.sh"
echo "      ./hack/workshop/verify-stack.sh"
