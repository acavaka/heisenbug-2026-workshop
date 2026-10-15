# BUG-TEMP-02: Двойной Pay → два Temporal workflow

- **Приоритет:** High
- **Статус:** Open
- **Компонент:** order-worker / Temporal WorkflowId
- **Автор:** oncall-sre
- **Создан:** 2026-09-17

## Описание

Клиент нажал Pay дважды. В Temporal UI два WorkflowId / разных RunId,
два Charge, два Ship/Email.

## Воспроизведение

```bash
curl -X POST http://127.0.0.1:8088/orders/duplicate
```

## Задача

Идемпотентность на уровне WorkflowId (один `order-{order_id}`),
`REJECT_DUPLICATE` / `TERMINATE_IF_RUNNING` — не уникальный id на каждый клик.
