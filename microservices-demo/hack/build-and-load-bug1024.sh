#!/usr/bin/env bash
# Build workshop images with BUG-1024 plant and load into Kind.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
TAG="${TAG:-workshop-bug1024}"
PCS_IMAGE="productcatalogservice:${TAG}"
FE_IMAGE="frontend:${TAG}"

kubectl config use-context "${CONTEXT}" >/dev/null

echo "==> Building ${PCS_IMAGE}..."
docker build -t "${PCS_IMAGE}" "${ROOT}/src/productcatalogservice"

echo "==> Building ${FE_IMAGE}..."
docker build -t "${FE_IMAGE}" "${ROOT}/src/frontend"

echo "==> Loading into Kind..."
kind load docker-image "${PCS_IMAGE}" --name "${CLUSTER_NAME}"
kind load docker-image "${FE_IMAGE}" --name "${CLUSTER_NAME}"

kubectl apply -f "${ROOT}/hack/workshop-bug1024-patch.yaml"

kubectl set image deployment/productcatalogservice "server=${PCS_IMAGE}"
kubectl set image deployment/frontend "server=${FE_IMAGE}"

kubectl patch deployment productcatalogservice --type=json -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
]' 2>/dev/null || kubectl patch deployment productcatalogservice --type=json -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
]'

kubectl patch deployment frontend --type=json -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
]' 2>/dev/null || kubectl patch deployment frontend --type=json -p='[
  {"op":"add","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
]'

# Ensure admin port + workshop env on catalog (idempotent-ish)
kubectl get deploy productcatalogservice -o json | \
  python3 -c '
import json,sys
d=json.load(sys.stdin)
c=d["spec"]["template"]["spec"]["containers"][0]
c["imagePullPolicy"]="Never"
ports=c.setdefault("ports",[])
if not any(p.get("containerPort")==8081 for p in ports):
    ports.append({"name":"admin","containerPort":8081})
env=c.setdefault("env",[])
def upsert(name,value):
    for e in env:
        if e.get("name")==name:
            e["value"]=value
            return
    env.append({"name":name,"value":value})
upsert("ADMIN_PORT","8081")
upsert("PRICE_CACHE_TTL_SECONDS","3600")
json.dump(d,sys.stdout)
' | kubectl apply -f -

echo "==> Waiting for rollouts..."
kubectl rollout status deployment/productcatalogservice --timeout=300s
kubectl rollout status deployment/frontend --timeout=300s
kubectl get pods -l 'app in (productcatalogservice,frontend)'
echo "OK. Run ./hack/ports.sh then ./hack/reproduce-bug-1024.sh"
