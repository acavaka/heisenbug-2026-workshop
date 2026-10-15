"""Оформление заказа."""

import logging
import uuid

from . import cart as cart_module
from . import payments
from .models import Cart, Order

logger = logging.getLogger("shopapi.checkout")


def create_order(cart: Cart, gateway_client) -> Order:
    total = cart_module.calculate_total(cart)
    order = Order(
        order_id=f"ORD-{uuid.uuid4().hex[:8]}",
        user_id=cart.user_id,
        items=list(cart.items),
        total=total,
    )
    logger.info("order created id=%s user=%s total=%.2f", order.order_id, order.user_id, order.total)
    payments.charge(order.order_id, order.total, gateway_client)
    order.status = "paid"
    logger.info("order paid id=%s", order.order_id)
    return order
