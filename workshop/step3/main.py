"""Дополнительное демо: четыре роли, один вердикт.

Основной маршрут e2e использует модель-оркестратор в agents/orchestrator.py:
модель выбирает роли и досбор, runtime ограничивает инструменты и проверяет вердикт.
Промпты и общие правила находятся в prompts/, реализация инструментов — в skills/.
Прежний фиксированный порядок agents/qai.py доступен через --mode workflow.

Запуск из workshop/: python step3/main.py --read-only BUG-TEMP-01
Используйте уже подготовленный стенд; эта команда не готовит учебный сбой.
Текущие четыре задания и тайминг: docs/workshop-exercises-draft.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from e2e import main as e2e_main  # noqa: E402

if __name__ == "__main__":
    e2e_main(sys.argv[1:] or ["BUG-TEMP-01"])

# Для сравнения режимов используйте --read-only --mode workflow.
# Подключение MCP выполняется по карточке exercises/mcp_connection/README.md.
