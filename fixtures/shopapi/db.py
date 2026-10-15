"""Наивное in-memory «хранилище». В реальной системе здесь был бы Postgres.

Для воркшопа важно только одно: db.get_product() всегда возвращает
АКТУАЛЬНЫЕ данные, в отличие от кэша в pricing.py.
"""

PRODUCTS: dict[str, dict] = {
    "SKU-4217": {"name": "Наушники AeroBuds Pro", "price": 12990.00},
    "SKU-1104": {"name": "Чехол для смартфона Grip+", "price": 990.00},
    "SKU-7730": {"name": "Умная колонка HomeTone", "price": 7490.00},
    "SKU-2951": {"name": "Кабель USB-C 2m", "price": 490.00},
    "SKU-8812": {"name": "Powerbank 20000 mAh", "price": 3290.00},
}


def get_product(sku: str) -> dict:
    if sku not in PRODUCTS:
        raise KeyError(f"Unknown SKU: {sku}")
    return PRODUCTS[sku]


def update_product_price(sku: str, new_price: float) -> None:
    get_product(sku)["price"] = new_price
