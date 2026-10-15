#!/usr/bin/env python3
"""Administrative stack demo without LLM; creates orders/workflows and traces.

Not a read-only readiness check. Use offline/verify_stand.py and check_http.py
for participant readiness; run this only during separately authorized preparation.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skills.tracker import tracker_list  # noqa: E402


def http_json(method: str, url: str, body: dict | None = None) -> dict | str:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def main() -> int:
    fail = 0
    print("=== tracker catalog ===")
    ids = tracker_list().splitlines()
    print("\n".join(ids))
    needed = {
        "BUG-1024",
        "INC-2088",
        "BUG-TEMP-01",
        "BUG-TEMP-02",
        "BUG-DB-01",
        "BUG-REDIS-01",
        "BUG-CURR-01",
        "BUG-SHIP-01",
        "BUG-REC-01",
        "BUG-REL-01",
    }
    missing = needed - set(ids)
    if missing:
        print("FAIL missing tracker ids:", missing)
        fail = 1
    else:
        print("OK tracker catalog")

    endpoints = {
        "frontend": "http://127.0.0.1:8080/_healthz",
        "grafana": "http://127.0.0.1:3000/api/health",
        "tempo": "http://127.0.0.1:3200/ready",
        "prometheus": "http://127.0.0.1:9090/-/ready",
        "temporal-ui": "http://127.0.0.1:8233/",
        "order-worker": "http://127.0.0.1:8088/healthz",
    }
    print("=== HTTP ===")
    for name, url in endpoints.items():
        ok = http_ok(url)
        print(("OK " if ok else "FAIL"), name, url)
        if not ok:
            fail = 1

    if http_ok("http://127.0.0.1:8088/healthz"):
        print("=== Temporal demos ===")
        ok_order = http_json(
            "POST",
            "http://127.0.0.1:8088/orders",
            {"user_id": "u-e2e", "amount_cents": 1500},
        )
        print("success:", ok_order)
        stuck = http_json("POST", "http://127.0.0.1:8088/orders/stuck")
        print("stuck:", stuck)
        dup = http_json("POST", "http://127.0.0.1:8088/orders/duplicate")
        print("duplicate:", dup)
        if not isinstance(ok_order, dict) or "workflow_id" not in ok_order:
            fail = 1
        if not isinstance(stuck, dict) or stuck.get("bug") != "BUG-TEMP-01":
            fail = 1
        if not isinstance(dup, dict) or stuck.get("bug") == "x":
            pass
        if not isinstance(dup, dict) or dup.get("bug") != "BUG-TEMP-02":
            fail = 1

    print("=== Tempo traces ===")
    # ensure demo traces exist
    inject = ROOT / "microservices-demo/hack/workshop/inject-demo-traces.py"
    if inject.exists():
        import subprocess

        subprocess.run([sys.executable, str(inject)], check=False)
    import time

    time.sleep(2)
    q = urllib.parse.urlencode({"q": "{}", "limit": "10"})
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:3200/api/search?{q}", timeout=10) as resp:
            search = resp.read().decode()
        print(search[:600])
        if "traceID" not in search and "traceId" not in search:
            print("FAIL no traces in Tempo")
            fail = 1
        else:
            print("OK Tempo traces present")
    except urllib.error.URLError as exc:
        print("FAIL Tempo search:", exc)
        fail = 1

    print()
    if fail:
        print("E2E FAILED")
        return 1
    print("E2E PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
