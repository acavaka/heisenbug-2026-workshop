"""Order saga Temporal workflows for the Heisenbug workshop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import (
        charge,
        compensate_charge,
        email_confirmation,
        reserve_cart,
        ship,
        update_order_status,
    )


@dataclass
class OrderInput:
    order_id: str
    user_id: str
    amount_cents: int
    inject_ship_fail: bool = False


@workflow.defn(name="OrderSaga")
class OrderSaga:
    """ReserveCart → Charge → Ship → Email, with compensate on mid-failure."""

    @workflow.run
    async def run(self, inp: OrderInput) -> dict:
        short = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )
        # BUG-TEMP-01: endless retries on Ship when inject_ship_fail
        ship_retry = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=0 if inp.inject_ship_fail else 3,
            backoff_coefficient=2.0,
        )

        await workflow.execute_activity(
            update_order_status,
            args=[inp.order_id, "RESERVED"],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )
        await workflow.execute_activity(
            reserve_cart,
            args=[inp.order_id, inp.user_id],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )

        payment_id = await workflow.execute_activity(
            charge,
            args=[inp.order_id, inp.amount_cents],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=short,
        )
        await workflow.execute_activity(
            update_order_status,
            args=[inp.order_id, "PAID", payment_id],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )

        try:
            await workflow.execute_activity(
                update_order_status,
                args=[inp.order_id, "SHIPPING_PENDING"],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=short,
            )
            tracking = await workflow.execute_activity(
                ship,
                args=[inp.order_id, inp.inject_ship_fail],
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=ship_retry,
            )
        except Exception:
            await workflow.execute_activity(
                compensate_charge,
                args=[inp.order_id, payment_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=short,
            )
            await workflow.execute_activity(
                update_order_status,
                args=[inp.order_id, "COMPENSATED"],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=short,
            )
            raise

        await workflow.execute_activity(
            update_order_status,
            args=[inp.order_id, "SHIPPED"],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )
        await workflow.execute_activity(
            email_confirmation,
            args=[inp.order_id, inp.user_id, tracking],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )
        await workflow.execute_activity(
            update_order_status,
            args=[inp.order_id, "COMPLETED"],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=short,
        )
        return {
            "order_id": inp.order_id,
            "payment_id": payment_id,
            "tracking": tracking,
            "status": "COMPLETED",
        }
