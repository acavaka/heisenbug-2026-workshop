"""Шаблон read-only инструмента: функция + schema + проверяемый результат.

Скопируйте, переименуйте my_tool, реализуйте _fetch_rows и зарегистрируйте
schema/impl в skills/__init__.py и tools роли. Затем python workshop/render.py.
Код сбора один для Python и редакторов. Подробности: docs/tool-authoring.md.
"""
from __future__ import annotations

import json
from harness.tool_result import ToolResult

MAX_LIMIT = 100
REQUEST_TIMEOUT_S = 15
SOURCE = 'my_service'  # логическое имя; не URL с токеном


def _fetch_rows(query: str, *, limit: int, timeout: int) -> list[str]:
    """TODO: read-only запрос; применить limit и timeout на стороне клиента API.

    Вернуть не более limit исходных строк без изменения их содержимого.
    Использовать параметры HTTP-клиента, а не склейку URL; секреты не возвращать.
    Для больших документов проектировать пагинацию/ссылки, не резать JSON.
    """
    raise NotImplementedError('Connect a read-only source')


def _result(status: str, items: list[str], *, truncated=False, error=None) -> ToolResult:
    return ToolResult(json.dumps({
        'status': status, 'source': SOURCE, 'items': items,
        'truncated': truncated, 'complete': False,
        'scope': 'bounded source query; absence outside this sample is unknown',
        'error': error,
    }, ensure_ascii=False), is_error=status == 'error')


def my_tool(query: str, limit: int = 50) -> ToolResult:
    """Ошибки отличаются от успешной пустой выборки; limit ограничивает строки."""
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        return _result('error', [], error='invalid_query')
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        return _result('error', [], error='invalid_limit')
    try:
        rows = _fetch_rows(query, limit=limit + 1, timeout=REQUEST_TIMEOUT_S)
        if (not isinstance(rows, list) or len(rows) > limit + 1
                or any(not isinstance(row, str) for row in rows)):
            return _result('error', [], error='invalid_source_response')
    except NotImplementedError:
        return _result('error', [], error='not_implemented')
    except Exception:
        # Не включать str(exc): там могут быть credentials или полный URL.
        return _result('error', [], error='source_unavailable')
    return _result('ok' if rows else 'empty', rows[:limit], truncated=len(rows) > limit)


MY_TOOLS_IMPL = {'my_tool': my_tool}
MY_TOOLS_SCHEMA = [{'type': 'function', 'function': {
    'name': 'my_tool',
    'description': (
        'TODO: укажите источник, синтаксис query и когда вызывать. '
        'Возвращает ограниченную выборку исходных строк; empty не доказывает '
        'отсутствие события, truncated означает отсечение строк. '
        'Не доказывает полноту истории или причину сбоя.'
    ),
    'parameters': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'query': {'type': 'string', 'minLength': 1, 'maxLength': 2000,
                      'description': 'TODO: формат и синтетический пример запроса'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': MAX_LIMIT,
                      'default': 50, 'description': 'Максимум возвращаемых строк'},
        },
        'required': ['query'],
    },
}}]
