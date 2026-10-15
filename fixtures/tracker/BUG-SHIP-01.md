# BUG-SHIP-01: Shipping quote 0 или огромный

- **Приоритет:** Low
- **Статус:** Open
- **Компонент:** shippingservice
- **Создан:** 2026-09-17

## Описание

Стоимость доставки иногда 0.00, иногда завышена на порядки для того же адреса.

## Улики

- Tempo spans `shippingservice`
- logs + `src/shippingservice`
