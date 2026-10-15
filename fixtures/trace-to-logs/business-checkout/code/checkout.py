"""Checkout amount calculation. Synthetic source snapshot."""
from decimal import Decimal


def total_cents(unit_price: str, quantity: int) -> int:
    price = Decimal(unit_price)
    return int(price) * 100 * quantity
