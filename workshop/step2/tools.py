"""Инструменты агента-исследователя логов.

Каждый инструмент — обычная Python-функция + JSON-схема, по которой LLM
понимает, что инструмент умеет и какие у него аргументы. Качество
description напрямую влияет на то, как агент пользуется инструментом.
"""

import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
LOGS_DIR = FIXTURES / "logs"

MAX_RESULT_LINES = 60  # защита контекста от «выкачай мне весь лог»


def list_log_files() -> str:
    files = sorted(LOGS_DIR.glob("*.log"))
    return "\n".join(
        f"{f.name} ({len(f.read_text(encoding='utf-8').splitlines())} строк)"
        for f in files
    )


def grep_logs(pattern: str, filename: str) -> str:
    path = LOGS_DIR / filename
    if not path.exists():
        return f"Файл {filename} не найден. Доступные: {list_log_files()}"
    matches = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(pattern, line, re.IGNORECASE):
            matches.append(f"{i}: {line}")
    if not matches:
        return f"По паттерну {pattern!r} ничего не найдено в {filename}"
    truncated = ""
    if len(matches) > MAX_RESULT_LINES:
        truncated = f"\n... показаны первые {MAX_RESULT_LINES} из {len(matches)} совпадений, уточните паттерн"
        matches = matches[:MAX_RESULT_LINES]
    return "\n".join(matches) + truncated


def read_log_window(filename: str, line_number: int, context: int = 10) -> str:
    path = LOGS_DIR / filename
    if not path.exists():
        return f"Файл {filename} не найден. Доступные: {list_log_files()}"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(0, line_number - 1 - context)
    end = min(len(lines), line_number + context)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))


LOG_TOOLS_IMPL = {
    "list_log_files": list_log_files,
    "grep_logs": grep_logs,
    "read_log_window": read_log_window,
}

LOG_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_log_files",
            "description": "Показать список доступных файлов логов с количеством строк.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_logs",
            "description": (
                "Поиск строк в файле логов по регулярному выражению "
                "(без учёта регистра). Возвращает строки с номерами. "
                "Используй точные паттерны: id заказов, sku, суммы, уровни WARN/ERROR."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Регулярное выражение"},
                    "filename": {"type": "string", "description": "Имя файла лога, например app-2026-06-16.log"},
                },
                "required": ["pattern", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_log_window",
            "description": (
                "Прочитать окно строк вокруг указанной строки лога — "
                "чтобы увидеть контекст найденного grep'ом события."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "line_number": {"type": "integer", "description": "Номер строки в центре окна"},
                    "context": {"type": "integer", "description": "Сколько строк до и после (по умолчанию 10)"},
                },
                "required": ["filename", "line_number"],
            },
        },
    },
]
