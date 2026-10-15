# BUG-REC-01: Recommendations «левые» товары

- **Приоритет:** Low
- **Статус:** Open
- **Компонент:** recommendationservice
- **Создан:** 2026-09-17

## Описание

На PDP рекомендуются товары, не связанные с текущим product_id
(или дубликаты текущего).

## Улики

- logs recommendationservice
- код `list_recommendations`
