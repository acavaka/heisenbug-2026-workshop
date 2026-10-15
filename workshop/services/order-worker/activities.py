"""Activities for OrderSaga — simulated side effects + Postgres status."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from temporalio import activity

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:workshop@postgres:5432/orders",
)


def _conn():
    import psycopg

    return psycopg.connect(DATABASE_URL)


@activity.defn
def reserve_cart(order_id: str, user_id: str) -> str:
    activity.logger.info("reserve_cart order=%s user=%s", order_id, user_id)
    return f"cart-reserved:{order_id}"


@activity.defn
def charge(order_id: str, amount_cents: int) -> str:
    payment_id = f"pay-{uuid.uuid4().hex[:10]}"
    activity.logger.info(
        "charge order=%s amount=%s payment_id=%s", order_id, amount_cents, payment_id
    )
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (payment_id, order_id, amount_cents, status)
                VALUES (%s, %s, %s, 'SUCCESS')
                ON CONFLICT DO NOTHING
                """,
                (payment_id, order_id, amount_cents),
            )
        conn.commit()
    return payment_id


@activity.defn
def ship(order_id: str, inject_fail: bool) -> str:
    activity.logger.info("ship order=%s inject_fail=%s", order_id, inject_fail)
    if inject_fail:
        raise RuntimeError(
            f"shipping carrier unavailable for {order_id} (BUG-TEMP-01 inject)"
        )
    return f"TRK-{order_id[-8:].upper()}"


@activity.defn
def email_confirmation(order_id: str, user_id: str, tracking: str) -> str:
    activity.logger.info(
        "email order=%s user=%s tracking=%s", order_id, user_id, tracking
    )
    return f"email-sent:{order_id}"


@activity.defn
def compensate_charge(order_id: str, payment_id: str) -> str:
    activity.logger.info("compensate_charge order=%s payment=%s", order_id, payment_id)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE payments SET status='REFUNDED' WHERE payment_id=%s",
                (payment_id,),
            )
        conn.commit()
    return f"refunded:{payment_id}"


@activity.defn
def update_order_status(
    order_id: str, status: str, payment_id: str | None = None
) -> str:
    activity.logger.info("update_order_status order=%s status=%s", order_id, status)
    now = datetime.now(timezone.utc)
    with _conn() as conn:
        with conn.cursor() as cur:
            if payment_id:
                cur.execute(
                    """
                    UPDATE orders
                    SET status=%s, updated_at=%s,
                        payment_ids = array_append(COALESCE(payment_ids, '{}'), %s)
                    WHERE order_id=%s
                    """,
                    (status, now, payment_id, order_id),
                )
            else:
                cur.execute(
                    "UPDATE orders SET status=%s, updated_at=%s WHERE order_id=%s",
                    (status, now, order_id),
                )
        conn.commit()
    return status
