"""Модели данных ShopAPI."""

from dataclasses import dataclass, field


@dataclass
class Product:
    sku: str
    name: str
    price: float


@dataclass
class CartItem:
    sku: str
    quantity: int


@dataclass
class Cart:
    user_id: str
    items: list[CartItem] = field(default_factory=list)
    promo_code: str | None = None


@dataclass
class Order:
    order_id: str
    user_id: str
    items: list[CartItem]
    total: float
    status: str = "created"


@dataclass
class Payment:
    payment_id: str
    order_id: str
    amount: float
    status: str
