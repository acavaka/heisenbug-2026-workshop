#!/usr/bin/env bash
# Port-forward workshop UIs/APIs to localhost.
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
kubectl config use-context "${CONTEXT}" >/dev/null

PIDS=()
cleanup() {
  for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done
}
trap cleanup EXIT

fwd() {
  local local_port="$1" svc="$2" remote="$3"
  echo "  http://127.0.0.1:${local_port}  <-  ${svc}:${remote}"
  kubectl port-forward --address=127.0.0.1 "svc/${svc}" "${local_port}:${remote}" >/tmp/pf-${svc}.log 2>&1 &
  PIDS+=($!)
}

echo "Workshop port-forwards (Ctrl+C to stop):"
fwd 8080 frontend 80
fwd 3000 grafana 3000
fwd 3200 tempo 3200
fwd 4317 tempo 4317
fwd 4318 tempo 4318
fwd 9090 prometheus 9090
fwd 8233 temporal-ui 8080
fwd 7233 temporal 7233
fwd 8088 order-worker 8088
fwd 5432 postgres 5432

echo
echo "  Boutique UI:    http://127.0.0.1:8080"
echo "  Grafana:        http://127.0.0.1:3000  (admin/admin)"
echo "  Tempo:          http://127.0.0.1:3200"
echo "  Prometheus:     http://127.0.0.1:9090"
echo "  Temporal UI:    http://127.0.0.1:8233"
echo "  order-worker:   http://127.0.0.1:8088"
echo "  Temporal gRPC:  127.0.0.1:7233"
echo "  Postgres:       127.0.0.1:5432  (postgres/workshop, db=orders)"
echo
wait
