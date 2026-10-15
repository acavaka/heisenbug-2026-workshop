#!/usr/bin/env bash
# Lead-only (needs network once): pull/build images, retag to boutique/*, save tars.
# Output: hack/offline/images/*.tar (+ optional images.tar.gz)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OFFLINE="$(cd "$(dirname "$0")" && pwd)"
LIST="${OFFLINE}/image-list.txt"
OUT="${OFFLINE}/images"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
WORKER_SRC="$(cd "${ROOT}/../workshop/services/order-worker" 2>/dev/null && pwd || true)"
if [[ -z "${WORKER_SRC}" || ! -d "${WORKER_SRC}" ]]; then
  WORKER_SRC="$(cd "${OFFLINE}/../../../workshop/services/order-worker" && pwd)"
fi

mkdir -p "${OUT}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }; }
need docker

echo "==> Build order-worker:workshop (local)"
docker build -t order-worker:workshop "${WORKER_SRC}"

echo "==> Optional BUG-1024 images (if Dockerfiles present)"
if [[ -d "${ROOT}/src/productcatalogservice" ]]; then
  docker build -t productcatalogservice:workshop-bug1024 "${ROOT}/src/productcatalogservice" || true
  docker build -t frontend:workshop-bug1024 "${ROOT}/src/frontend" || true
fi

saved=()
while IFS= read -r line || [[ -n "${line}" ]]; do
  line="$(echo "${line}" | sed 's/#.*//' | xargs)"
  [[ -z "${line}" ]] && continue
  src="${line%%|*}"
  local="${line##*|}"
  echo "==> ${src}  ->  ${local}"
  if ! docker image inspect "${src}" >/dev/null 2>&1; then
    echo "    pulling ${src}..."
    docker pull "${src}"
  fi
  docker tag "${src}" "${local}"
  # also keep bug1024 local tags if built
  safe="$(echo "${local}" | tr '/:' '__')"
  tar="${OUT}/${safe}.tar"
  echo "    saving ${tar}"
  docker save -o "${tar}" "${local}"
  saved+=("${local}")
done < "${LIST}"

# Always include bug1024 if they exist locally
for img in productcatalogservice:workshop-bug1024 frontend:workshop-bug1024; do
  if docker image inspect "${img}" >/dev/null 2>&1; then
    local="boutique/${img}"
    docker tag "${img}" "${local}"
    safe="$(echo "${local}" | tr '/:' '__')"
    tar="${OUT}/${safe}.tar"
    echo "==> extra ${local} -> ${tar}"
    docker save -o "${tar}" "${local}"
    saved+=("${local}")
  fi
done

echo "==> Packing archive (optional download for USB)"
ARCHIVE="${OFFLINE}/workshop-images.tar.gz"
tar -czf "${ARCHIVE}" -C "${OUT}" .
ls -lh "${OUT}"/*.tar | awk '{print $5, $9}'
echo "Archive: ${ARCHIVE} ($(du -h "${ARCHIVE}" | awk '{print $1}'))"
echo "Images saved: ${#saved[@]}"
echo "Next (online machine with Kind): still use load-images.sh + up-offline.sh"
echo "Distribute: ${ARCHIVE} or the images/ folder on USB (NOT via git)."
