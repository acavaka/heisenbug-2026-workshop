#!/usr/bin/env bash
# Drive real Boutique traffic → real logs + OTEL spans (when ENABLE_TRACING=1).
# Usage: ./hack/workshop/generate-traffic.sh [rounds]
set -euo pipefail

FRONTEND="${FRONTEND_URL:-http://127.0.0.1:8080}"
ROUNDS="${1:-5}"
PRODUCTS=(OLJCESPC7Z 66VCHSJNUP 1YMWWN1N4O L9ECAV7KEM 2ZYFJ3GM2N)
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "Traffic → ${FRONTEND}  rounds=${ROUNDS}"
echo "Cookie jar: ${COOKIE_JAR}"

year=$(( $(date +%Y) + 1 ))

for r in $(seq 1 "${ROUNDS}"); do
  echo "==> round ${r}/${ROUNDS}"
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null "${FRONTEND}/" || true

  pid="${PRODUCTS[$(( (r - 1) % ${#PRODUCTS[@]} ))]}"
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    "${FRONTEND}/product/${pid}" || true

  # currency switch → currencyservice
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    -X POST "${FRONTEND}/setCurrency" \
    -d "currency_code=EUR" || true

  # add to cart → cartservice + catalog
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    -X POST "${FRONTEND}/cart" \
    -d "product_id=${pid}&quantity=1" || true

  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    "${FRONTEND}/cart" || true

  # checkout → checkout, payment, shipping, email, currency, cart, catalog
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    -X POST "${FRONTEND}/cart/checkout" \
    --data-urlencode "email=workshop${r}@example.com" \
    --data-urlencode "street_address=1600 Amphitheatre Parkway" \
    --data-urlencode "zip_code=94043" \
    --data-urlencode "city=Mountain View" \
    --data-urlencode "state=CA" \
    --data-urlencode "country=United States" \
    --data-urlencode "credit_card_number=4432-8015-6152-0454" \
    --data-urlencode "credit_card_expiration_month=1" \
    --data-urlencode "credit_card_expiration_year=${year}" \
    --data-urlencode "credit_card_cvv=672" || true

  # intentional miss → error-ish logs on catalog/frontend
  curl -sf -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" -o /dev/null \
    "${FRONTEND}/product/DOESNOTEXIST999" || true

  sleep 0.5
done

echo
echo "Done. Check:"
echo "  kubectl logs deploy/frontend --tail=30"
echo "  kubectl logs deploy/checkoutservice --tail=30"
echo "  Grafana Explore → Tempo → Search (recent)"
echo "  Also: python3 hack/workshop/inject-demo-traces.py  # full synthetic graph"
