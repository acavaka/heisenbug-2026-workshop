# BUG-REL-01: Деградация после релиза

- **Приоритет:** Medium
- **Статус:** Open
- **Компонент:** release / config
- **Создан:** 2026-09-17

## Описание

После выката тега `v0.10.0-workshop` выросла latency checkout и число 5xx.
В release notes упомянут эксперимент с `GATEWAY_TIMEOUT`.

## Улики

- fixtures/github/release-v0.10.0-workshop.md
- Prometheus latency
- GitHub MCP / git history
