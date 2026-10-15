#!/usr/bin/env bash
# Rewrite upstream manifests to boutique/* local images + imagePullPolicy: Never.
# Writes into hack/offline/generated/ (gitignored).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OFFLINE="$(cd "$(dirname "$0")" && pwd)"
GEN="${OFFLINE}/generated"
mkdir -p "${GEN}/workshop"

# Boutique release manifest: retarget gcr + redis/busybox, force Never
python3 - <<'PY' "${ROOT}/release/kubernetes-manifests.yaml" "${GEN}/kubernetes-manifests-offline.yaml"
import re, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
repl = {
    "gcr.io/google-samples/microservices-demo/": "boutique/",
    "image: redis:alpine": "image: boutique/redis:alpine",
    "image: busybox:latest": "image: boutique/busybox:latest",
}
for a, b in repl.items():
    text = text.replace(a, b)

# Ensure every container with image: boutique/ has imagePullPolicy: Never
# Insert after each boutique image line if not already followed by pull policy nearby.
lines = text.splitlines(True)
out = []
i = 0
while i < len(lines):
    line = lines[i]
    out.append(line)
    m = re.match(r"^(\s*)image:\s*(boutique/\S+)\s*$", line)
    if m:
        indent = m.group(1)
        # peek next few lines for existing imagePullPolicy on same container
        window = "".join(lines[i + 1 : i + 8])
        if "imagePullPolicy:" not in window.split("image:")[0]:
            out.append(f"{indent}imagePullPolicy: Never\n")
    i += 1
open(dst, "w", encoding="utf-8").write("".join(out))
print(f"wrote {dst}")
PY

# Workshop stack yamls
rewrite_ws() {
  local src="$1" dst="$2"
  sed -e 's|image: postgres:15-alpine|image: boutique/postgres:15-alpine|' \
      -e 's|image: grafana/tempo:2.6.1|image: boutique/tempo:2.6.1|' \
      -e 's|image: prom/prometheus:v2.54.1|image: boutique/prometheus:v2.54.1|' \
      -e 's|image: grafana/grafana:11.2.0|image: boutique/grafana:11.2.0|' \
      -e 's|image: temporalio/auto-setup:1.25.2|image: boutique/temporal:1.25.2|' \
      -e 's|image: temporalio/ui:2.31.2|image: boutique/temporal-ui:2.31.2|' \
      -e 's|image: order-worker:workshop|image: boutique/order-worker:workshop|' \
      "${src}" > "${dst}"
  # inject imagePullPolicy Never after boutique images
  python3 - <<'PY' "${dst}"
import re, sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
out = []
i = 0
while i < len(lines):
    line = lines[i]
    out.append(line)
    m = re.match(r"^(\s*)image:\s*(boutique/\S+)\s*$", line)
    if m:
        indent = m.group(1)
        window = "".join(lines[i + 1 : i + 8])
        if "imagePullPolicy:" not in window.split("image:")[0]:
            out.append(f"{indent}imagePullPolicy: Never\n")
    i += 1
open(path, "w", encoding="utf-8").write("".join(out))
PY
}

for f in postgres.yaml tempo.yaml prometheus.yaml grafana.yaml temporal.yaml; do
  rewrite_ws "${ROOT}/hack/workshop/${f}" "${GEN}/workshop/${f}"
done

# order-worker from workshop service
if [[ -f "${ROOT}/../workshop/services/order-worker/k8s.yaml" ]]; then
  rewrite_ws "${ROOT}/../workshop/services/order-worker/k8s.yaml" "${GEN}/workshop/order-worker.yaml"
elif [[ -f "${OFFLINE}/../../../workshop/services/order-worker/k8s.yaml" ]]; then
  rewrite_ws "${OFFLINE}/../../../workshop/services/order-worker/k8s.yaml" "${GEN}/workshop/order-worker.yaml"
fi

# BUG-1024 patch: point to boutique workshop tags if present
if [[ -f "${ROOT}/hack/workshop-bug1024-patch.yaml" ]]; then
  cp "${ROOT}/hack/workshop-bug1024-patch.yaml" "${GEN}/workshop-bug1024-patch.yaml"
fi

echo "Generated offline manifests in ${GEN}"
