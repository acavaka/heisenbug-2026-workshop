#!/usr/bin/env bash
# Deploy workshop stack: Postgres, Tempo, Prometheus, Grafana, Temporal, order-worker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HACK="$(cd "$(dirname "$0")" && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
WORKER_SRC="${ROOT}/../workshop/services/order-worker"
# monorepo: heisenbug_2026/microservices-demo/hack/workshop → heisenbug_2026/workshop
WORKER_SRC="$(cd "$(dirname "$0")/../../../workshop/services/order-worker" && pwd)"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' not found in PATH" >&2
    exit 1
  }
}

need docker
need kind
need kubectl

kubectl config use-context "${CONTEXT}" >/dev/null

echo "==> Postgres"
kubectl apply -f "${HACK}/postgres.yaml"
kubectl wait --for=condition=available --timeout=180s deployment/postgres || true
# Wait ready
for i in $(seq 1 36); do
  if kubectl exec deploy/postgres -- pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

echo "==> Tempo / Prometheus / Grafana"
kubectl apply -f "${HACK}/tempo.yaml"
kubectl apply -f "${HACK}/prometheus.yaml"
kubectl apply -f "${HACK}/grafana.yaml"

echo "==> Temporal"
kubectl apply -f "${HACK}/temporal.yaml"
kubectl wait --for=condition=available --timeout=300s deployment/temporal || true
kubectl wait --for=condition=available --timeout=180s deployment/temporal-ui || true

echo "==> Build + load order-worker"
docker build -t order-worker:workshop "${WORKER_SRC}"
kind load docker-image order-worker:workshop --name "${CLUSTER_NAME}"
kubectl apply -f "${WORKER_SRC}/k8s.yaml"
kubectl rollout restart deployment/order-worker 2>/dev/null || true
kubectl wait --for=condition=available --timeout=180s deployment/order-worker || true

echo "==> Enable OTEL tracing → Tempo"
for dep in frontend checkoutservice paymentservice productcatalogservice \
           currencyservice emailservice recommendationservice; do
  kubectl set env "deployment/${dep}" \
    ENABLE_TRACING=1 \
    COLLECTOR_SERVICE_ADDR=tempo:4317 \
    2>/dev/null || true
done
# Node OTLP exporters often want host:port without scheme
kubectl set env deployment/paymentservice \
  ENABLE_TRACING=1 \
  COLLECTOR_SERVICE_ADDR=tempo:4317 \
  OTEL_EXPORTER_OTLP_ENDPOINT=tempo:4317 \
  2>/dev/null || true

echo "==> Waiting for core workshop pods..."
kubectl wait --for=condition=available --timeout=180s \
  deployment/tempo deployment/prometheus deployment/grafana \
  deployment/postgres deployment/temporal-ui || true

echo
kubectl get pods -l 'app in (postgres,tempo,prometheus,grafana,temporal,temporal-ui,order-worker)'
echo
echo "Done. Next: ${HACK}/ports-workshop.sh"
echo "Addresses: see docs/sources-and-ports.md"
