#!/usr/bin/env bash
# Tear down Kind cluster (or only Boutique manifests).
# Usage: ./hack/down.sh [--manifests-only]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
MANIFEST="${ROOT}/release/kubernetes-manifests.yaml"

if [[ "${1:-}" == "--manifests-only" ]]; then
  kubectl --context "${CONTEXT}" delete -f "${MANIFEST}" --ignore-not-found
  echo "Manifests deleted from ${CONTEXT}"
  exit 0
fi

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  kind delete cluster --name "${CLUSTER_NAME}"
  echo "Deleted Kind cluster '${CLUSTER_NAME}'"
else
  echo "Cluster '${CLUSTER_NAME}' not found"
fi
