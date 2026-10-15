# BUG-CURR-01: Неверная конвертация EUR/USD

- **Приоритет:** Medium
- **Статус:** Open
- **Компонент:** currencyservice
- **Создан:** 2026-09-17

## Описание

При переключении валюты на EUR итоговая сумма на checkout «прыгает»
или не соответствует курсу из `currency_conversion.json`.

## Улики

- logs `currencyservice`
- Prometheus / frontend currency cookie
- код `src/currencyservice`
