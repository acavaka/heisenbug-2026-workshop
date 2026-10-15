"""Генератор логов для воркшопа. Детерминированный (фиксированный seed).

Создаёт:
  logs/app-2026-06-16.log       — след бага BUG-1024 (кэш цен)
  logs/app-2026-06-30.log       — фон приложения в окно инцидента INC-2088
  logs/payments-2026-06-30.log  — след инцидента INC-2088 (двойные списания)

Запуск:  python generate_logs.py
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(20260707)

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

SKUS = ["SKU-4217", "SKU-1104", "SKU-7730", "SKU-2951", "SKU-8812"]
PRICES = {
    "SKU-4217": 12990.00,
    "SKU-1104": 990.00,
    "SKU-7730": 7490.00,
    "SKU-2951": 490.00,
    "SKU-8812": 3290.00,
}
NEW_PRICE_4217 = 10990.00

ENDPOINTS = [
    "GET /api/products", "GET /api/products/{sku}", "POST /api/cart/items",
    "GET /api/cart", "POST /api/checkout", "GET /api/orders/{id}",
]


def ts(base: datetime, offset_s: float) -> str:
    return (base + timedelta(seconds=offset_s)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def uid() -> str:
    return f"u-{random.randint(10000, 99999)}"


def hexid(n: int = 8) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def noise_line(base: datetime, offset_s: float) -> str:
    kind = random.random()
    t = ts(base, offset_s)
    if kind < 0.55:
        ep = random.choice(ENDPOINTS)
        ms = random.randint(8, 240)
        return f"{t} INFO shopapi.http {ep} status=200 user={uid()} duration_ms={ms}"
    if kind < 0.70:
        sku = random.choice(SKUS)
        return f"{t} DEBUG shopapi.catalog product view sku={sku} user={uid()}"
    if kind < 0.80:
        return f"{t} INFO shopapi.auth session refreshed user={uid()}"
    if kind < 0.88:
        return f"{t} WARN shopapi.http GET /api/products/{{sku}} status=404 sku=SKU-{random.randint(1000, 9999)} user={uid()}"
    if kind < 0.94:
        return f"{t} DEBUG shopapi.metrics heartbeat ok pool_size=12 in_use={random.randint(1, 9)}"
    return f"{t} INFO shopapi.search query=\"{random.choice(['наушники', 'чехол', 'кабель', 'колонка', 'powerbank'])}\" results={random.randint(0, 42)} user={uid()}"


# ---------------------------------------------------------------- BUG-1024

def gen_bug_1024() -> None:
    """День 2026-06-16. В 10:03 админ уценил SKU-4217 с 12990 до 10990.

    До 10:03 всё консистентно. После — страница товара (display price, без
    кэша) показывает 10990, а корзина (get_price, кэш прогрет до уценки)
    считает по 12990. У пользователей с холодным кэшем инстанса всё ок —
    отсюда «нестабильное воспроизведение».
    """
    base = datetime(2026, 6, 16, 9, 30, 0)
    lines: list[tuple[float, str]] = []
    horizon = 3.5 * 3600  # 09:30 - 13:00

    t = 0.0
    while t < horizon:
        t += random.uniform(0.5, 4.0)
        lines.append((t, noise_line(base, t)))

    # Прогрев кэша цен до уценки (важная улика: cache miss в 09:41)
    warm = (11 * 60) + 12.0  # 09:41:12
    lines.append((warm, f"{ts(base, warm)} DEBUG shopapi.pricing cache miss sku=SKU-4217 fetched price=12990.00"))
    for sku in ["SKU-7730", "SKU-1104"]:
        warm += random.uniform(20, 90)
        lines.append((warm, f"{ts(base, warm)} DEBUG shopapi.pricing cache miss sku={sku} fetched price={PRICES[sku]:.2f}"))

    # Уценка через админку в 10:03:17
    upd = (33 * 60) + 17.0
    lines.append((upd, f"{ts(base, upd)} INFO shopapi.admin price updated sku=SKU-4217 old=12990.00 new=10990.00 operator=admin-04"))

    # После уценки: страница товара показывает новую цену, корзина — старую.
    # Все жалобы укладываются в окно жизни кэша (до warm + 3600).
    for i in range(14):
        off = upd + 300 + i * random.uniform(90, 130)
        user = uid()
        view = off - random.uniform(30, 120)
        lines.append((view, f"{ts(base, view)} INFO shopapi.catalog display price sku=SKU-4217 price=10990.00 user={user}"))
        lines.append((off - 0.4, f"{ts(base, off - 0.4)} DEBUG shopapi.pricing cache hit sku=SKU-4217 price=12990.00 age_s={int(off - warm)}"))
        lines.append((off - 0.3, f"{ts(base, off - 0.3)} DEBUG shopapi.cart sku=SKU-4217 qty=1 price=12990.0"))
        lines.append((off, f"{ts(base, off)} INFO shopapi.cart cart total user={user} total=12990.00"))

    # Пара «здоровых» пользователей на инстансе с холодным кэшем (после 10:41,
    # т.е. кэш там наполнился уже НОВОЙ ценой) — источник «нестабильности»
    for i in range(3):
        off = upd + 2400 + i * random.uniform(400, 700)
        user = uid()
        lines.append((off - 0.5, f"{ts(base, off - 0.5)} DEBUG shopapi.pricing cache miss sku=SKU-4217 fetched price=10990.00"))
        lines.append((off - 0.3, f"{ts(base, off - 0.3)} DEBUG shopapi.cart sku=SKU-4217 qty=1 price=10990.0"))
        lines.append((off, f"{ts(base, off)} INFO shopapi.cart cart total user={user} total=10990.00"))

    # Через час после прогрева (10:41+) TTL истекает — жалобы затихают
    exp = warm + 3600 + 5
    lines.append((exp, f"{ts(base, exp)} DEBUG shopapi.pricing cache expired sku=SKU-4217 age_s=3605"))
    lines.append((exp + 0.1, f"{ts(base, exp + 0.1)} DEBUG shopapi.pricing cache miss sku=SKU-4217 fetched price=10990.00"))

    # Другие товары считаются корректно (сужают зону поиска)
    for i in range(8):
        off = random.uniform(0, horizon)
        sku = random.choice(["SKU-1104", "SKU-2951", "SKU-8812"])
        user = uid()
        lines.append((off, f"{ts(base, off)} INFO shopapi.cart cart total user={user} total={PRICES[sku]:.2f}"))

    lines.sort(key=lambda x: x[0])
    out = LOGS_DIR / "app-2026-06-16.log"
    out.write_text("\n".join(line for _, line in lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(lines)} lines)")


# ---------------------------------------------------------------- INC-2088

def gen_inc_2088() -> None:
    """Вечер 2026-06-30. Релиз 2.14.0 в 18:20 уменьшил таймаут шлюза 10s -> 2s.

    С 18:35 шлюз деградирует (ответы 1.5-4s). Часть запросов укладывается,
    часть ловит клиентский таймаут -> ретрай с НОВЫМ request_id -> двойное
    списание, если первый запрос на шлюзе всё же прошёл.
    """
    base = datetime(2026, 6, 30, 18, 0, 0)
    app_lines: list[tuple[float, str]] = []
    pay_lines: list[tuple[float, str]] = []
    horizon = 90 * 60  # 18:00 - 19:30

    t = 0.0
    while t < horizon:
        t += random.uniform(0.4, 3.0)
        app_lines.append((t, noise_line(base, t)))

    dep = 20 * 60.0
    app_lines.append((dep, f"{ts(base, dep)} INFO shopapi.deploy release 2.14.0 started"))
    app_lines.append((dep + 45, f"{ts(base, dep + 45)} INFO shopapi.deploy release 2.14.0 completed config: GATEWAY_TIMEOUT_SECONDS=2 (was 10)"))

    def payment(off: float, degraded: bool) -> float:
        order = f"ORD-{hexid()}"
        user = uid()
        sku = random.choice(SKUS)
        amount = PRICES[sku]
        app_lines.append((off - 1.0, f"{ts(base, off - 1.0)} INFO shopapi.cart cart total user={user} total={amount:.2f}"))
        app_lines.append((off, f"{ts(base, off)} INFO shopapi.checkout order created id={order} user={user} total={amount:.2f}"))

        rid1 = hexid(32)
        pay_lines.append((off + 0.1, f"{ts(base, off + 0.1)} INFO shopapi.payments charge attempt=1 order={order} amount={amount:.2f} request_id={rid1}"))

        if not degraded:
            latency = random.uniform(0.2, 0.9)
            pid = f"pay_{hexid(12)}"
            pay_lines.append((off + 0.1 + latency, f"{ts(base, off + 0.1 + latency)} INFO shopapi.payments gateway response request_id={rid1} status=succeeded payment={pid} latency_ms={int(latency * 1000)}"))
            pay_lines.append((off + 0.2 + latency, f"{ts(base, off + 0.2 + latency)} INFO shopapi.payments charge ok order={order} payment={pid}"))
            app_lines.append((off + 0.3 + latency, f"{ts(base, off + 0.3 + latency)} INFO shopapi.checkout order paid id={order}"))
            return off + latency + 1

        # Деградация: ответ шлюза 1.5-4s при клиентском таймауте 2s
        gw_latency = random.uniform(1.5, 4.0)
        if gw_latency < 2.0:
            pid = f"pay_{hexid(12)}"
            pay_lines.append((off + 0.1 + gw_latency, f"{ts(base, off + 0.1 + gw_latency)} INFO shopapi.payments gateway response request_id={rid1} status=succeeded payment={pid} latency_ms={int(gw_latency * 1000)}"))
            pay_lines.append((off + 0.2 + gw_latency, f"{ts(base, off + 0.2 + gw_latency)} INFO shopapi.payments charge ok order={order} payment={pid}"))
            app_lines.append((off + 0.3 + gw_latency, f"{ts(base, off + 0.3 + gw_latency)} INFO shopapi.checkout order paid id={order}"))
            return off + gw_latency + 1

        # Клиентский таймаут на первой попытке
        pay_lines.append((off + 2.1, f"{ts(base, off + 2.1)} WARN shopapi.payments charge timeout attempt=1 order={order} request_id={rid1}"))
        # ...но шлюз первый платёж всё-таки провёл (ответ пришёл в закрытое соединение)
        pid1 = f"pay_{hexid(12)}"
        pay_lines.append((off + 0.1 + gw_latency, f"{ts(base, off + 0.1 + gw_latency)} INFO shopapi.payments gateway late response request_id={rid1} status=succeeded payment={pid1} latency_ms={int(gw_latency * 1000)} (connection already closed)"))

        # Ретрай с НОВЫМ request_id
        rid2 = hexid(32)
        r2 = off + 2.2
        pay_lines.append((r2, f"{ts(base, r2)} INFO shopapi.payments charge attempt=2 order={order} amount={amount:.2f} request_id={rid2}"))
        lat2 = random.uniform(0.8, 1.9)
        pid2 = f"pay_{hexid(12)}"
        pay_lines.append((r2 + lat2, f"{ts(base, r2 + lat2)} INFO shopapi.payments gateway response request_id={rid2} status=succeeded payment={pid2} latency_ms={int(lat2 * 1000)}"))
        pay_lines.append((r2 + lat2 + 0.1, f"{ts(base, r2 + lat2 + 0.1)} INFO shopapi.payments charge ok order={order} payment={pid2}"))
        app_lines.append((r2 + lat2 + 0.2, f"{ts(base, r2 + lat2 + 0.2)} INFO shopapi.checkout order paid id={order}"))
        return r2 + lat2 + 1

    # Платежи до деградации (18:05-18:35) — всё чисто
    off = 5 * 60.0
    while off < 35 * 60:
        off = payment(off, degraded=False) + random.uniform(40, 120)

    # Окно деградации 18:35-19:05
    deg_start = 35 * 60.0
    pay_lines.append((deg_start, f"{ts(base, deg_start)} WARN shopapi.payments gateway latency elevated p50_ms=1800 p99_ms=4100"))
    while off < 65 * 60:
        off = payment(off, degraded=True) + random.uniform(30, 90)

    pay_lines.append((65 * 60.0, f"{ts(base, 65 * 60.0)} INFO shopapi.payments gateway latency recovered p50_ms=240"))

    # После восстановления — снова чисто
    while off < horizon - 60:
        off = payment(off, degraded=False) + random.uniform(60, 150)

    # Пример из инцидента: ORD-a3f81c02 / u-77012 / 7490 x2 (вставляем явно)
    ex = 47 * 60.0
    rid_a, rid_b = hexid(32), hexid(32)
    app_lines.append((ex - 1, f"{ts(base, ex - 1)} INFO shopapi.cart cart total user=u-77012 total=7490.00"))
    app_lines.append((ex, f"{ts(base, ex)} INFO shopapi.checkout order created id=ORD-a3f81c02 user=u-77012 total=7490.00"))
    pay_lines.append((ex + 0.1, f"{ts(base, ex + 0.1)} INFO shopapi.payments charge attempt=1 order=ORD-a3f81c02 amount=7490.00 request_id={rid_a}"))
    pay_lines.append((ex + 2.1, f"{ts(base, ex + 2.1)} WARN shopapi.payments charge timeout attempt=1 order=ORD-a3f81c02 request_id={rid_a}"))
    pay_lines.append((ex + 2.2, f"{ts(base, ex + 2.2)} INFO shopapi.payments charge attempt=2 order=ORD-a3f81c02 amount=7490.00 request_id={rid_b}"))
    pay_lines.append((ex + 3.1, f"{ts(base, ex + 3.1)} INFO shopapi.payments gateway late response request_id={rid_a} status=succeeded payment=pay_1f2c9a80e3b4 latency_ms=3050 (connection already closed)"))
    pay_lines.append((ex + 3.6, f"{ts(base, ex + 3.6)} INFO shopapi.payments gateway response request_id={rid_b} status=succeeded payment=pay_77d0c4b2a911 latency_ms=1400"))
    pay_lines.append((ex + 3.7, f"{ts(base, ex + 3.7)} INFO shopapi.payments charge ok order=ORD-a3f81c02 payment=pay_77d0c4b2a911"))
    app_lines.append((ex + 3.8, f"{ts(base, ex + 3.8)} INFO shopapi.checkout order paid id=ORD-a3f81c02"))

    app_lines.sort(key=lambda x: x[0])
    pay_lines.sort(key=lambda x: x[0])
    out_app = LOGS_DIR / "app-2026-06-30.log"
    out_pay = LOGS_DIR / "payments-2026-06-30.log"
    out_app.write_text("\n".join(line for _, line in app_lines) + "\n", encoding="utf-8")
    out_pay.write_text("\n".join(line for _, line in pay_lines) + "\n", encoding="utf-8")
    print(f"wrote {out_app} ({len(app_lines)} lines)")
    print(f"wrote {out_pay} ({len(pay_lines)} lines)")


if __name__ == "__main__":
    gen_bug_1024()
    gen_inc_2088()
