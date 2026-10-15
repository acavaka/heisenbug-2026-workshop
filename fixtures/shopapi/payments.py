"""Интеграция с платёжным шлюзом. Здесь живёт root cause инцидента INC-2088.

При таймауте от шлюза делаем ретрай, но БЕЗ ключа идемпотентности.
Если первый запрос на самом деле дошёл до шлюза (а таймаут случился на
ответе), ретрай создаёт ВТОРОЕ списание с тем же order_id.
"""

import logging
import uuid

logger = logging.getLogger("shopapi.payments")

GATEWAY_TIMEOUT_SECONDS = 2  # после релиза 2.14.0 уменьшен с 10 до 2
MAX_RETRIES = 2


def charge(order_id: str, amount: float, gateway_client) -> str:
    """Списывает деньги. Возвращает payment_id."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        # BUG: request_id генерируется заново на каждой попытке,
        # шлюз не может дедуплицировать повторный запрос.
        request_id = str(uuid.uuid4())
        try:
            logger.info(
                "charge attempt=%s order=%s amount=%.2f request_id=%s",
                attempt, order_id, amount, request_id,
            )
            payment_id = gateway_client.charge(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                timeout=GATEWAY_TIMEOUT_SECONDS,
            )
            logger.info("charge ok order=%s payment=%s", order_id, payment_id)
            return payment_id
        except TimeoutError as exc:
            last_error = exc
            logger.warning(
                "charge timeout attempt=%s order=%s request_id=%s",
                attempt, order_id, request_id,
            )
    raise RuntimeError(f"payment failed for order {order_id}") from last_error
