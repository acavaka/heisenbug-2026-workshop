# QAI — воркшоп для тестировщиков

Формат: 60 минут вводной и настройки, 30 минут перерыв, 60 минут практики.
Начните с [prework](docs/participant-prework-draft.md), затем откройте
[четыре задания](docs/workshop-exercises-draft.md). [Указатель документации](docs/README.md).

## Что вы собираете

Модель-оркестратор выбирает роли analyzer, investigator и checker, задаёт им вопросы
и решает, нужен ли досбор. Python ограничивает инструменты и бюджет; общий валидатор
проверяет вердикт. В редакторах проверка выполняется через application MCP или k8sgpt MCP.
Инструкции, учебные данные и критерии работы общие для Python, Codex, Claude Code и Cursor.

Практика: проверить расследование → улучшить инструкцию → подключить MCP → реализовать
trace_to_logs. Данные BUG-LAB-01 — файловый replay; live-инфраструктура — отдельный qai-training.
Boutique и order-worker используются только на чтение. Учебные неисправности не исправляем.

## Подготовка

Полный набор зависимостей выдаётся отдельно от Git: образы, wheels, инструменты,
установщики и контрольные суммы. Одного clone для установки без скачиваний недостаточно.
Проверенный маршрут: macOS Apple Silicon / Python 3.12.6 / установленный Docker 4.42.1.
Установка приложенного Docker 4.91.0/VMM на чистом Mac и Windows/Linux/Intel не подтверждены.
[MacBook с USB](docs/new-macbook-offline.md) · [Windows x64 / WSL2: комплект и границы проверки](docs/setup-windows.md).

Подготовьте выбранный клиент и авторизацию модели заранее. Подписка редактора не требует
API-ключа для MCP; облачной модели нужен интернет. Стандартный Python использует отдельный
API-профиль, файловое задание также поддерживает транспорт Codex по подписке.

Из корня проекта в подготовленном окружении:

```bash
workshop/.venv/bin/python workshop/offline/check.py
workshop/.venv/bin/python workshop/e2e.py --read-only BUG-1024
```

Первая команда проверяет локальную готовность без модели и live-кластера; вторая запускает
реальное расследование с настроенной моделью и уже подготовленным стендом.
Прежний фиксированный маршрут доступен явно через --mode workflow.

## Материалы и проверки

- [Архитектура](docs/model-orchestrator.md), [доказательства](docs/evidence-contract.md).
- [Редакторы](docs/multi-provider.md), [application MCP](docs/application-mcp.md), [k8sgpt MCP](docs/k8sgpt-mcp.md).
- [Свои инструменты](docs/tool-authoring.md), [eval](docs/agent-eval.md), [перенос на работу](docs/monday-replay-guide.md).

В публичном составе нет решений, HINTS, INSTRUCTOR, презентаций, резервных вердиктов
и ключей поведенческого eval. Подсказки выдаёт ведущий по запросу.
Исходные учебные данные, код исследуемых сервисов и проверки контракта открыты намеренно.
Проверка контракта не означает правильный root cause: выводы сверяются с источниками человеком.

```bash
workshop/.venv/bin/python -m unittest discover -s tests/workshop -v
python3 workshop/render.py --check
```

Это публичные тесты механизмов, без приватного набора решений и ключей eval.
Свой результат trace_to_logs проверяйте командой check из карточки; до реализации TODO FAIL ожидаем.
Локальные результаты сохраняйте в workshop/.local/, секреты и kubeconfig не коммитьте.

## Структура

workshop/ — runtime, промпты, инструменты, MCP и задания; fixtures/ — синтетические источники;
tests/ — публичные проверки; docs/ — инструкции участника и технические справочники.
AGENTS.md — общие правила, CLAUDE.md и адаптеры .agents/.claude/.cursor генерируются render.py.
Код Boutique уже в microservices-demo/, order-worker — в workshop/services/order-worker/.
