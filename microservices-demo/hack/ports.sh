#!/usr/bin/env bash
# Port-forward Boutique frontend to http://127.0.0.1:8080
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
LOCAL_PORT="${LOCAL_PORT:-8080}"

kubectl config use-context "${CONTEXT}" >/dev/null
echo "Forwarding svc/frontend -> http://127.0.0.1:${LOCAL_PORT}"
echo "Stop with Ctrl+C"
exec kubectl port-forward --address=127.0.0.1 svc/frontend "${LOCAL_PORT}:80"
