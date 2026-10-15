#!/usr/bin/env python3
"""
Full-path demo traces for Grafana Tempo:
  success — homepage + PDP + cart + PlaceOrder through all Boutique services
  error   — same path, Charge fails (card_declined)

Also prints TraceIDs for Explore → Tempo.
"""

from __future__ import annotations

import json
import random
import time
import urllib.request


def _hex_id(bits: int) -> str:
    return random.getrandbits(bits).to_bytes(bits // 8, "big").hex()


def make_span(
    trace_id: str,
    span_id: str,
    name: str,
    service: str,
    start_ns: int,
    duration_ns: int,
    parent: str | None = None,
    status_code: int = 1,
    attrs: dict | None = None,
) -> dict:
    s: dict = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": 3 if parent else 2,  # CLIENT/SERVER-ish
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(start_ns + duration_ns),
        "attributes": [
            {"key": k, "value": {"stringValue": str(v)}} for k, v in (attrs or {}).items()
        ],
        "status": {"code": status_code},
    }
    if parent:
        s["parentSpanId"] = parent
    return {
        "resource": {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": service}},
                {
                    "key": "service.namespace",
                    "value": {"stringValue": "online-boutique"},
                },
            ]
        },
        "scopeSpans": [{"spans": [s]}],
    }


def post_otlp(resource_spans: list) -> None:
    body = json.dumps({"resourceSpans": resource_spans}).encode()
    for url in (
        "http://127.0.0.1:4318/v1/traces",
        "http://127.0.0.1:3200/v1/traces",
    ):
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"OTLP ok → {url} ({resp.status})")
                return
        except Exception as exc:
            print(f"skip {url}: {exc}")
    raise SystemExit("failed to post OTLP to Tempo (is ports-workshop.sh running?)")


def build_place_order_graph(
    trace_id: str,
    t0: int,
    *,
    fail_payment: bool,
) -> list:
    """
    Realistic PlaceOrder fan-out:

      frontend
        ├─ recommendationservice
        ├─ adservice
        └─ checkoutservice.PlaceOrder
              ├─ cartservice.GetCart
              ├─ productcatalogservice.GetProduct  (x2)
              ├─ currencyservice.Convert
              ├─ paymentservice.Charge            [may ERROR]
              ├─ shippingservice.ShipOrder
              └─ emailservice.SendOrderConfirmation
    """
    rs: list = []
    t = t0

    fe = _hex_id(64)
    rs.append(
        make_span(
            trace_id,
            fe,
            "HTTP POST /cart/checkout",
            "frontend",
            t,
            120_000_000,
            attrs={"http.route": "/cart/checkout", "scenario": "full-checkout"},
        )
    )

    # parallel-ish side calls from frontend
    for svc, name, dt in (
        ("recommendationservice", "ListRecommendations", 12_000_000),
        ("adservice", "GetAds", 8_000_000),
    ):
        sid = _hex_id(64)
        rs.append(
            make_span(trace_id, sid, name, svc, t + 2_000_000, dt, parent=fe)
        )

    co = _hex_id(64)
    rs.append(
        make_span(
            trace_id,
            co,
            "PlaceOrder",
            "checkoutservice",
            t + 15_000_000,
            95_000_000,
            parent=fe,
            attrs={"rpc.method": "PlaceOrder"},
        )
    )

    children = [
        ("cartservice", "GetCart", 10_000_000, 1, None),
        ("productcatalogservice", "GetProduct", 14_000_000, 1, {"product.id": "OLJCESPC7Z"}),
        ("productcatalogservice", "GetProduct", 11_000_000, 1, {"product.id": "66VCHSJNUP"}),
        ("currencyservice", "Convert", 9_000_000, 1, {"currency": "USD"}),
        (
            "paymentservice",
            "Charge",
            25_000_000,
            2 if fail_payment else 1,
            {"error": "card_declined"} if fail_payment else {"payment.status": "SUCCESS"},
        ),
    ]
    offset = 20_000_000
    for svc, name, dur, code, attrs in children:
        sid = _hex_id(64)
        rs.append(
            make_span(
                trace_id,
                sid,
                name,
                svc,
                t + offset,
                dur,
                parent=co,
                status_code=code,
                attrs=attrs,
            )
        )
        offset += dur + 1_000_000

    if not fail_payment:
        for svc, name, dur in (
            ("shippingservice", "ShipOrder", 18_000_000),
            ("emailservice", "SendOrderConfirmation", 15_000_000),
        ):
            sid = _hex_id(64)
            rs.append(
                make_span(trace_id, sid, name, svc, t + offset, dur, parent=co)
            )
            offset += dur + 1_000_000
    else:
        # compensate / abort markers for teaching
        sid = _hex_id(64)
        rs.append(
            make_span(
                trace_id,
                sid,
                "PlaceOrder.failed",
                "checkoutservice",
                t + offset,
                5_000_000,
                parent=co,
                status_code=2,
                attrs={"error": "payment_failed"},
            )
        )

    return rs


def build_browse_graph(trace_id: str, t0: int) -> list:
    """Home + PDP: frontend → catalog, currency, recommendations, ads."""
    rs: list = []
    fe = _hex_id(64)
    rs.append(
        make_span(
            trace_id,
            fe,
            "HTTP GET /product/OLJCESPC7Z",
            "frontend",
            t0,
            40_000_000,
            attrs={"http.route": "/product/{id}", "scenario": "browse-pdp"},
        )
    )
    offset = 2_000_000
    for svc, name, dur, attrs in (
        ("productcatalogservice", "GetProduct", 12_000_000, {"product.id": "OLJCESPC7Z"}),
        ("currencyservice", "Convert", 6_000_000, {"currency": "EUR"}),
        ("recommendationservice", "ListRecommendations", 10_000_000, None),
        ("adservice", "GetAds", 7_000_000, None),
    ):
        sid = _hex_id(64)
        rs.append(
            make_span(
                trace_id,
                sid,
                name,
                svc,
                t0 + offset,
                dur,
                parent=fe,
                attrs=attrs,
            )
        )
        offset += dur
    return rs


def main() -> None:
    now = time.time_ns()
    all_rs: list = []

    tid_ok = _hex_id(128)
    all_rs.extend(build_place_order_graph(tid_ok, now, fail_payment=False))
    print(f"SUCCESS full-checkout trace_id={tid_ok}")

    tid_err = _hex_id(128)
    all_rs.extend(build_place_order_graph(tid_err, now + 200_000_000, fail_payment=True))
    print(f"ERROR   full-checkout trace_id={tid_err}")

    tid_browse = _hex_id(128)
    all_rs.extend(build_browse_graph(tid_browse, now + 400_000_000))
    print(f"BROWSE  pdp           trace_id={tid_browse}")

    post_otlp(all_rs)
    print()
    print("Grafana → Explore → Tempo → вставьте TraceID")
    print(f"  success: {tid_ok}")
    print(f"  error:   {tid_err}")
    print(f"  browse:  {tid_browse}")


if __name__ == "__main__":
    main()
