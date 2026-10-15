"""Задание 4 (35–55 минут практики): корреляция файлового trace и логов.

Меняйте correlate и description. Adapters уже готовы; живые источники не вызываются.
Карточка: workshop/exercises/trace_to_logs/README.md.
"""
from exercises.trace_to_logs.adapters import investigate, tool_text


def correlate(rows, since, until, trace_id, extra_keys, limit):
    """TODO участника: вернуть {matches, context, truncated}.

    rows: готовые записи {time: aware datetime, ids: dict, raw: str, line: int}.
    1. Оставьте time в замкнутом окне [since, until].
    2. matches: trace_id точно равен ids['trace_id'] ИЛИ один extra_keys точно
       равен значению request_id/order_id. Подстрока в raw НЕ является совпадением.
       У каждой строки укажите matched_by — список имён совпавших полей.
    3. context: только строки окна БЕЗ идентификаторов; это не доказанная корреляция.
       Строки с чужими идентификаторами исключите из обеих групп.
    4. Выведите {raw, line, matched_by} без datetime, ограничьте каждую группу limit.
       truncated=True, если пришлось обрезать хотя бы одну группу.
    """
    raise NotImplementedError('Implement correlation, not file/network access')


def trace_to_logs(trace_id: str, extra_keys: list[str] | None = None) -> str:
    return tool_text(investigate(correlate, trace_id, extra_keys))


TRACE_LOGS_TOOLS_IMPL = {'trace_to_logs': trace_to_logs}
TRACE_LOGS_TOOLS_SCHEMA = [{'type':'function','function':{
    'name':'trace_to_logs',
    'description':'Учебный файловый replay: связывает известный trace_id с логами сервисов. TODO: уточните когда применять, чем matches отличаются от context и что означает неполнота. Не обращается к живому Tempo/Kubernetes.',
    'parameters':{'type':'object','properties':{'trace_id':{'type':'string'},'extra_keys':{'type':'array','items':{'type':'string'}}},'required':['trace_id'],'additionalProperties':False}
}}]
