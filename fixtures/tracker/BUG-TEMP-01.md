# BUG-TEMP-01: Заказ зависает в SHIPPING_PENDING

- **Приоритет:** High
- **Статус:** Open
- **Компонент:** order-worker / Temporal OrderSaga
- **Автор:** oncall-sre
- **Создан:** 2026-09-17

## Описание

После успешной оплаты заказ часами остаётся в статусе `SHIPPING_PENDING`.
В Temporal UI workflow Running, activity `ship` бесконечно ретраится.

## Воспроизведение

```bash
curl -X POST http://127.0.0.1:8088/orders/stuck
```

Смотреть Temporal UI http://127.0.0.1:8233 и Postgres `orders.status`.

## Задача

Найти причину retry storm / отсутствия compensate и предложить фикс
(finite RetryPolicy + compensate_charge).
