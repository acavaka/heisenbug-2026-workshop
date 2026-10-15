#!/usr/bin/env bash
# Save images already present in a running Kind node (no registry pull).
# Useful when the lead already ran up.sh / up-workshop once online.
set -euo pipefail

OFFLINE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OFFLINE}/images"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
NODE="${CLUSTER_NAME}-control-plane"
LIST="${OFFLINE}/image-list.txt"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }; }
need docker

mkdir -p "${OUT}"

if ! docker inspect "${NODE}" >/dev/null 2>&1; then
  echo "ERROR: Kind node container '${NODE}' not running. Start Docker + Kind first," >&2
  echo "       or use export-images.sh (pulls once from registries)." >&2
  exit 1
fi

# Map: local_ref -> possible refs inside the node
# We import into host docker via `ctr images export` + `docker load` when possible,
# else `crictl pull` is NOT used — only export what exists.

echo "==> Images in Kind node:"
docker exec "${NODE}" crictl images

echo "==> Exporting known images to ${OUT}"
# For each local boutique tag, find a matching image in the node and export
while IFS= read -r line || [[ -n "${line}" ]]; do
  line="$(echo "${line}" | sed 's/#.*//' | xargs)"
  [[ -z "${line}" ]] && continue
  src="${line%%|*}"
  local="${line##*|}"
  safe="$(echo "${local}" | tr '/:' '__')"
  tar="${OUT}/${safe}.tar"

  # Prefer host docker if already tagged
  if docker image inspect "${local}" >/dev/null 2>&1 || docker image inspect "${src}" >/dev/null 2>&1; then
    [[ "$(docker image inspect "${local}" >/dev/null 2>&1 && echo y)" != "y" ]] && docker tag "${src}" "${local}"
    echo "  host save ${local}"
    docker save -o "${tar}" "${local}"
    continue
  fi

  # Try export from containerd in the node (src name as stored in cluster)
  echo "  trying node export for ${src} -> ${local}"
  tmp="/tmp/${safe}.tar"
  if docker exec "${NODE}" ctr -n k8s.io images export "${tmp}" "${src}" 2>/dev/null; then
    docker cp "${NODE}:${tmp}" "${tar}"
    docker exec "${NODE}" rm -f "${tmp}" || true
    docker load -i "${tar}"
    docker tag "${src}" "${local}" 2>/dev/null || true
    # re-save under boutique name only
    if docker image inspect "${local}" >/dev/null 2>&1; then
      docker save -o "${tar}" "${local}"
    fi
    echo "  ok ${tar}"
  else
    echo "  SKIP (not in node and not on host): ${src}"
  fi
done < "${LIST}"

# order-worker / bug1024 from host if present
for img in order-worker:workshop productcatalogservice:workshop-bug1024 frontend:workshop-bug1024; do
  if docker image inspect "${img}" >/dev/null 2>&1; then
    local="boutique/${img}"
    docker tag "${img}" "${local}"
    safe="$(echo "${local}" | tr '/:' '__')"
    docker save -o "${OUT}/${safe}.tar" "${local}"
    echo "  saved ${local}"
  fi
done

echo "==> Packing workshop-images.tar.gz"
tar -czf "${OFFLINE}/workshop-images.tar.gz" -C "${OUT}" .
ls -lh "${OUT}"/*.tar 2>/dev/null | awk '{print $5, $9}' || true
du -h "${OFFLINE}/workshop-images.tar.gz"
echo "Done. Distribute images/ or workshop-images.tar.gz (not via git)."
