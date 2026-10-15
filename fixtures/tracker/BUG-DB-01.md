# BUG-DB-01: UI «оплачено», в БД PENDING

- **Приоритет:** High
- **Статус:** Open
- **Компонент:** checkout / Postgres orders
- **Создан:** 2026-09-17

## Описание

Пользователь видит confirmation, но в таблице `orders` статус `PENDING`
(`ORD-demo-pending`). Рассинхрон UI и БД.

## Улики

```sql
SELECT * FROM orders WHERE order_id='ORD-demo-pending';
```

- Tempo PlaceOrder chain
- skill `postgres_query`
