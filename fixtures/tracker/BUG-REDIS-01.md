# BUG-REDIS-01: Пустая / чужая корзина

- **Приоритет:** Medium
- **Статус:** Open
- **Компонент:** cartservice / redis-cart
- **Создан:** 2026-09-17

## Описание

После добавления товаров корзина иногда пустая или показывает чужие позиции
(перепутан session id / Redis key).

## Улики

- `kubectl logs deploy/cartservice`
- Redis keys через `kubectl exec deploy/redis-cart -- redis-cli KEYS '*'`
- Frontend cookie `shop_session-id`
