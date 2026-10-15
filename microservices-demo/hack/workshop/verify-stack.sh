#!/usr/bin/env bash
# Verify workshop stack: health, Temporal demos, Tempo traces.
set -euo pipefail

BASE_OW="${ORDER_WORKER_URL:-http://127.0.0.1:8088}"
TEMPO="${TEMPO_URL:-http://127.0.0.1:3200}"
GRAFANA="${GRAFANA_URL:-http://127.0.0.1:3000}"
PROM="${PROM_URL:-http://127.0.0.1:9090}"
TEMPORAL_UI="${TEMPORAL_UI_URL:-http://127.0.0.1:8233}"
FRONTEND="${FRONTEND_URL:-http://127.0.0.1:8080}"

fail=0
check() {
  local name="$1" url="$2"
  if curl -sf -o /dev/null --max-time 5 "$url"; then
    echo "OK  ${name}: ${url}"
  else
    echo "FAIL ${name}: ${url}"
    fail=1
  fi
}

echo "==> HTTP health"
check frontend "${FRONTEND}/_healthz"
check grafana "${GRAFANA}/api/health"
check tempo "${TEMPO}/ready"
check prometheus "${PROM}/-/ready"
check temporal-ui "${TEMPORAL_UI}/"
check order-worker "${BASE_OW}/healthz"

echo "==> Temporal: success order"
OK_JSON=$(curl -sf -X POST "${BASE_OW}/orders" -H 'Content-Type: application/json' \
  -d '{"user_id":"u-e2e","amount_cents":1999}')
echo "$OK_JSON"
WF_OK=$(echo "$OK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['workflow_id'])")

echo "==> Temporal: BUG-TEMP-01 stuck"
STUCK=$(curl -sf -X POST "${BASE_OW}/orders/stuck")
echo "$STUCK"

echo "==> Temporal: BUG-TEMP-02 duplicate"
DUP=$(curl -sf -X POST "${BASE_OW}/orders/duplicate")
echo "$DUP"

echo "==> Generate Boutique traffic for traces"
curl -sf -o /dev/null "${FRONTEND}/" || true
curl -sf -o /dev/null "${FRONTEND}/product/OLJCESPC7Z" || true
curl -sf -o /dev/null "${FRONTEND}/product/DOESNOTEXIST999" || true
# Force a few more hits
for i in 1 2 3; do
  curl -sf -o /dev/null "${FRONTEND}/" || true
  sleep 1
done

echo "==> Wait for spans to flush to Tempo..."
sleep 8

echo "==> Tempo search (Tag: service.name)"
# Tempo Search HTTP API
SEARCH=$(curl -sf --get "${TEMPO}/api/search" --data-urlencode "q={}" --data-urlencode "limit=5" || true)
echo "${SEARCH:0:500}"
if echo "$SEARCH" | grep -q traceID; then
  echo "OK  Tempo has traces"
else
  echo "WARN Tempo search empty — trying otlp inject fallback"
  # Inject a synthetic multi-span trace via OTLP HTTP if boutique didn't emit
  python3 "$(dirname "$0")/inject-demo-traces.py" || fail=1
  sleep 3
  SEARCH2=$(curl -sf --get "${TEMPO}/api/search" --data-urlencode "q={}" --data-urlencode "limit=5" || true)
  echo "${SEARCH2:0:500}"
  if echo "$SEARCH2" | grep -q traceID; then
    echo "OK  Tempo has demo traces"
  else
    echo "FAIL Tempo still empty"
    fail=1
  fi
fi

echo "==> Workflow id from success path: ${WF_OK}"
echo
if [[ "$fail" -eq 0 ]]; then
  echo "VERIFY PASSED"
  exit 0
else
  echo "VERIFY FAILED"
  exit 1
fi
