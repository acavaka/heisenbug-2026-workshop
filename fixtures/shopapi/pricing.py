"""Расчёт цен. Здесь живёт root cause бага BUG-1024.

Кэш цен наполняется при первом обращении и живёт PRICE_CACHE_TTL_SECONDS.
При обновлении цены через админку (db.update_product_price) кэш НЕ
инвалидируется, поэтому корзина считает сумму по старой цене, пока не
истечёт TTL. Страница товара кэш не использует и показывает новую цену —
отсюда расхождение, на которое жалуются пользователи.
"""

import time

from . import db

PRICE_CACHE_TTL_SECONDS = 3600

_price_cache: dict[str, tuple[float, float]] = {}  # sku -> (price, cached_at)


def get_price(sku: str) -> float:
    """Цена для расчёта корзины (с кэшем)."""
    now = time.time()
    if sku in _price_cache:
        price, cached_at = _price_cache[sku]
        if now - cached_at < PRICE_CACHE_TTL_SECONDS:
            return price
    price = db.get_product(sku)["price"]
    _price_cache[sku] = (price, now)
    return price


def get_display_price(sku: str) -> float:
    """Цена для страницы товара (без кэша — ходит в БД напрямую)."""
    return db.get_product(sku)["price"]
