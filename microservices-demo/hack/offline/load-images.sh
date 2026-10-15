#!/usr/bin/env bash
# Offline: docker load all tars, then kind load into cluster (no registry pulls).
set -euo pipefail

OFFLINE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OFFLINE}/images"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
LIST="${OFFLINE}/image-list.txt"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }; }
need docker
need kind

if [[ ! -d "${OUT}" ]] || ! ls "${OUT}"/*.tar >/dev/null 2>&1; then
  # try unpack archive
  if [[ -f "${OFFLINE}/workshop-images.tar.gz" ]]; then
    echo "==> Unpacking workshop-images.tar.gz..."
    mkdir -p "${OUT}"
    tar -xzf "${OFFLINE}/workshop-images.tar.gz" -C "${OUT}"
  else
    echo "ERROR: no ${OUT}/*.tar and no workshop-images.tar.gz" >&2
    echo "Ask the lead for the offline image pack (USB / shared drive)." >&2
    exit 1
  fi
fi

echo "==> docker load"
for tar in "${OUT}"/*.tar; do
  echo "  loading $(basename "${tar}")"
  docker load -i "${tar}"
done

# Ensure Kind cluster exists (kindest/node must already be loaded into docker)
if ! kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "==> Creating Kind cluster '${CLUSTER_NAME}' (uses local kindest/node image)..."
  # Prefer never pulling if image present
  export KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER="${KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER:-}"
  kind create cluster --name "${CLUSTER_NAME}" --image kindest/node:v1.32.2
else
  echo "==> Kind cluster '${CLUSTER_NAME}' already exists"
fi

echo "==> kind load docker-image (into node)"
while IFS= read -r line || [[ -n "${line}" ]]; do
  line="$(echo "${line}" | sed 's/#.*//' | xargs)"
  [[ -z "${line}" ]] && continue
  local="${line##*|}"
  if docker image inspect "${local}" >/dev/null 2>&1; then
    echo "  kind load ${local}"
    kind load docker-image "${local}" --name "${CLUSTER_NAME}"
  fi
done < "${LIST}"

# bug1024 extras
for img in boutique/productcatalogservice:workshop-bug1024 boutique/frontend:workshop-bug1024; do
  if docker image inspect "${img}" >/dev/null 2>&1; then
    echo "  kind load ${img}"
    kind load docker-image "${img}" --name "${CLUSTER_NAME}"
  fi
done

echo "OK. Images in Docker + Kind. Next: ./up-offline.sh (apply manifests only) or continue from up-offline.sh"
