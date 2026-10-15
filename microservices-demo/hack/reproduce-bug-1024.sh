#!/usr/bin/env bash
# Reproduce BUG-1024: product page shows new price, cart keeps cached GetProduct price.
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-qai-boutique}"
CONTEXT="kind-${CLUSTER_NAME}"
PRODUCT_ID="${PRODUCT_ID:-OLJCESPC7Z}"  # Sunglasses
OLD_UNITS="${OLD_UNITS:-19}"
OLD_NANOS="${OLD_NANOS:-990000000}"
NEW_UNITS="${NEW_UNITS:-15}"
NEW_NANOS="${NEW_NANOS:-990000000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:8080}"
COOKIE_JAR="$(mktemp)"

cleanup() {
  rm -f "${COOKIE_JAR}"
  [[ -n "${ADMIN_PF_PID:-}" ]] && kill "${ADMIN_PF_PID}" 2>/dev/null || true
}
trap cleanup EXIT

kubectl config use-context "${CONTEXT}" >/dev/null

echo "==> Checking frontend at ${FRONTEND_URL}"
if ! curl -sf -o /dev/null "${FRONTEND_URL}/"; then
  echo "Frontend not reachable. Start: ./hack/ports.sh" >&2
  exit 1
fi

echo "==> Port-forward productcatalog admin :18081"
kubectl port-forward --address=127.0.0.1 svc/productcatalogservice 18081:8081 >/tmp/pcs-admin-pf.log 2>&1 &
ADMIN_PF_PID=$!
sleep 2

echo "==> Warm GetProduct cache via cart flow (add ${PRODUCT_ID})"
# Hit product page (ListProducts — live) then add to cart (later GetProduct)
curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null "${FRONTEND_URL}/product/${PRODUCT_ID}"
curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
  -X POST "${FRONTEND_URL}/cart" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data "product_id=${PRODUCT_ID}&quantity=1"
curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null "${FRONTEND_URL}/cart"

echo "==> Update catalog price ${OLD_UNITS}.${OLD_NANOS} -> ${NEW_UNITS} (cache NOT invalidated)"
curl -sf -X POST \
  "http://127.0.0.1:18081/admin/update_price?id=${PRODUCT_ID}&units=${NEW_UNITS}&nanos=${NEW_NANOS}"
echo

echo "==> Product page (ListProducts / live):"
curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${FRONTEND_URL}/product/${PRODUCT_ID}" \
  | grep -oE '\$[0-9]+\.[0-9]+' | head -5 || true

echo "==> Cart page (GetProduct / cached):"
curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "${FRONTEND_URL}/cart" \
  | grep -oE '\$[0-9]+\.[0-9]+' | head -10 || true

echo
echo "==> Recent productcatalogservice logs (look for cache hit/miss + price updated):"
kubectl logs deploy/productcatalogservice --tail=40 | grep -E 'cache hit|cache miss|price updated' || \
  kubectl logs deploy/productcatalogservice --tail=40

echo
echo "Done. Expected: product page ~\$${NEW_UNITS}.99, cart still ~\$${OLD_UNITS}.99 until TTL."
echo "Agent hints: kubectl logs deploy/productcatalogservice | grep cache"
