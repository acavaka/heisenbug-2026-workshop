"""Промокоды. Намеренно простые и БЕЗ багов — ложный след для агента гипотез."""

PROMOS = {
    "SALE10": 0.10,
    "VIP15": 0.15,
}


def apply_promo(total: float, code: str) -> float:
    discount = PROMOS.get(code.upper(), 0.0)
    return total * (1 - discount)
