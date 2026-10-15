"""HTTP API + Temporal worker entrypoint for OrderSaga."""

from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from aiohttp import web
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker

from activities import (
    charge,
    compensate_charge,
    email_confirmation,
    reserve_cart,
    ship,
    update_order_status,
)
from workflows import OrderInput, OrderSaga

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal:7233")
TASK_QUEUE = os.getenv("TASK_QUEUE", "order-saga")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:workshop@postgres:5432/orders",
)
HTTP_PORT = int(os.getenv("HTTP_PORT", "8088"))


def _upsert_order(
    order_id: str,
    user_id: str,
    amount_cents: int,
    workflow_id: str,
    run_id: str,
    status: str = "STARTED",
) -> None:
    import psycopg

    now = datetime.now(timezone.utc)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (order_id, user_id, status, amount_cents, workflow_id, run_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO UPDATE SET
                  status=EXCLUDED.status,
                  workflow_id=EXCLUDED.workflow_id,
                  run_id=EXCLUDED.run_id,
                  updated_at=EXCLUDED.updated_at
                """,
                (order_id, user_id, status, amount_cents, workflow_id, run_id, now, now),
            )
        conn.commit()


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "order-worker"})


async def start_order(request: web.Request) -> web.Response:
    client: Client = request.app["client"]
    body = await request.json() if request.can_read_body else {}
    order_id = body.get("order_id") or f"ORD-{uuid.uuid4().hex[:10]}"
    user_id = body.get("user_id", "u-demo")
    amount_cents = int(body.get("amount_cents", 7490))
    inject = bool(body.get("inject_ship_fail", False))
    # Default: stable WorkflowId per order (idempotent). BUG-TEMP-02 overrides.
    unique = bool(body.get("unique_workflow_id", False))
    workflow_id = (
        f"order-{order_id}-{uuid.uuid4().hex[:6]}" if unique else f"order-{order_id}"
    )

    handle = await client.start_workflow(
        OrderSaga.run,
        OrderInput(order_id, user_id, amount_cents, inject),
        id=workflow_id,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE
        if unique
        else WorkflowIDReusePolicy.REJECT_DUPLICATE,
    )
    _upsert_order(
        order_id, user_id, amount_cents, workflow_id, handle.result_run_id or ""
    )
    return web.json_response(
        {
            "order_id": order_id,
            "workflow_id": workflow_id,
            "run_id": handle.result_run_id,
            "inject_ship_fail": inject,
        },
        status=201,
    )


async def stuck_order(request: web.Request) -> web.Response:
    """BUG-TEMP-01: Ship fails forever → SHIPPING_PENDING / retry storm."""
    request._body = b'{"inject_ship_fail": true}'  # type: ignore[attr-defined]
    # Rebuild as proper JSON start
    client: Client = request.app["client"]
    order_id = f"ORD-stuck-{uuid.uuid4().hex[:8]}"
    user_id = "u-stuck"
    amount_cents = 7490
    workflow_id = f"order-{order_id}"
    handle = await client.start_workflow(
        OrderSaga.run,
        OrderInput(order_id, user_id, amount_cents, True),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    _upsert_order(
        order_id, user_id, amount_cents, workflow_id, handle.result_run_id or "",
        status="SHIPPING_PENDING",
    )
    return web.json_response(
        {
            "bug": "BUG-TEMP-01",
            "order_id": order_id,
            "workflow_id": workflow_id,
            "run_id": handle.result_run_id,
            "expected": "workflow stuck retrying Ship; status SHIPPING_PENDING",
        },
        status=201,
    )


async def duplicate_pay(request: web.Request) -> web.Response:
    """BUG-TEMP-02: double-click Pay → two workflows / two run ids."""
    client: Client = request.app["client"]
    base_order = f"ORD-dup-{uuid.uuid4().hex[:8]}"
    user_id = "u-doubleclick"
    amount_cents = 7490
    results = []
    for i in range(2):
        # Wrong idempotency: unique workflow id per click
        order_id = f"{base_order}-click{i+1}"
        workflow_id = f"order-{base_order}-run{i+1}"
        handle = await client.start_workflow(
            OrderSaga.run,
            OrderInput(order_id, user_id, amount_cents, False),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        _upsert_order(
            order_id, user_id, amount_cents, workflow_id, handle.result_run_id or ""
        )
        results.append(
            {
                "order_id": order_id,
                "workflow_id": workflow_id,
                "run_id": handle.result_run_id,
            }
        )
    return web.json_response(
        {
            "bug": "BUG-TEMP-02",
            "base": base_order,
            "workflows": results,
            "expected": "two WorkflowIds / run ids for one user Pay action",
        },
        status=201,
    )


async def get_order(request: web.Request) -> web.Response:
    import psycopg

    order_id = request.match_info["order_id"]
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT order_id, user_id, status, amount_cents, payment_ids, workflow_id, run_id "
                "FROM orders WHERE order_id=%s",
                (order_id,),
            )
            row = cur.fetchone()
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(
        {
            "order_id": row[0],
            "user_id": row[1],
            "status": row[2],
            "amount_cents": row[3],
            "payment_ids": row[4],
            "workflow_id": row[5],
            "run_id": row[6],
        }
    )


async def main() -> None:
    client = await Client.connect(TEMPORAL_HOST)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[OrderSaga],
        activities=[
            reserve_cart,
            charge,
            ship,
            email_confirmation,
            compensate_charge,
            update_order_status,
        ],
        activity_executor=ThreadPoolExecutor(max_workers=8),
    )

    app = web.Application()
    app["client"] = client
    app.router.add_get("/healthz", health)
    app.router.add_post("/orders", start_order)
    app.router.add_post("/orders/stuck", stuck_order)
    app.router.add_post("/orders/duplicate", duplicate_pay)
    app.router.add_get("/orders/{order_id}", get_order)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    print(f"order-worker HTTP on :{HTTP_PORT}, Temporal {TEMPORAL_HOST}", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
