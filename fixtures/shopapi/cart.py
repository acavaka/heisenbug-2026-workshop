"""Корзина: расчёт итоговой суммы."""

import logging

from . import pricing
from .models import Cart
from .promo import apply_promo

logger = logging.getLogger("shopapi.cart")


def calculate_total(cart: Cart) -> float:
    total = 0.0
    for item in cart.items:
        price = pricing.get_price(item.sku)
        total += price * item.quantity
        logger.debug("sku=%s qty=%s price=%s", item.sku, item.quantity, price)
    if cart.promo_code:
        total = apply_promo(total, cart.promo_code)
    logger.info("cart total user=%s total=%.2f", cart.user_id, total)
    return round(total, 2)
