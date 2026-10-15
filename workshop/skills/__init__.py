"""Реестр всех скиллов. Один скилл = функция + JSON-схема.

Роли берут подмножество по именам из frontmatter prompts/*.md (tools_for),
CLI фильтрует реестр при --read-only; редакторные адаптеры используют этот профиль.
Динамические MCP-инструменты investigator подключаются отдельно от статического реестра.
"""

from __future__ import annotations

from skills.cluster_logs import CLUSTER_LOGS_TOOLS_IMPL, CLUSTER_LOGS_TOOLS_SCHEMA
from skills.code import CODE_TOOLS_IMPL, CODE_TOOLS_SCHEMA
from skills.context_fixtures import CONTEXT_TOOLS_IMPL, CONTEXT_TOOLS_SCHEMA
from skills.k8sgpt_skill import K8SGPT_TOOLS_IMPL, K8SGPT_TOOLS_SCHEMA
from skills.postgres_query import POSTGRES_TOOLS_IMPL, POSTGRES_TOOLS_SCHEMA
from skills.prom import PROM_TOOLS_IMPL, PROM_TOOLS_SCHEMA
from skills.runbook import RUNBOOK_TOOLS_IMPL, RUNBOOK_TOOLS_SCHEMA
from skills.tempo import TEMPO_TOOLS_IMPL, TEMPO_TOOLS_SCHEMA
from skills.temporal_inspect import TEMPORAL_TOOLS_IMPL, TEMPORAL_TOOLS_SCHEMA
from skills.trace_logs import TRACE_LOGS_TOOLS_IMPL, TRACE_LOGS_TOOLS_SCHEMA
from skills.tracker import TRACKER_TOOLS_IMPL, TRACKER_TOOLS_SCHEMA

ALL_TOOLS_IMPL: dict = {
    **TRACKER_TOOLS_IMPL,
    **CONTEXT_TOOLS_IMPL,
    **CLUSTER_LOGS_TOOLS_IMPL,
    **TEMPO_TOOLS_IMPL,
    **TRACE_LOGS_TOOLS_IMPL,
    **PROM_TOOLS_IMPL,
    **POSTGRES_TOOLS_IMPL,
    **TEMPORAL_TOOLS_IMPL,
    **K8SGPT_TOOLS_IMPL,
    **CODE_TOOLS_IMPL,
    **RUNBOOK_TOOLS_IMPL,  # пишущий: не выдаётся LLM-ролям, вызывает оркестратор
}

ALL_TOOLS_SCHEMA: list = (
    TRACKER_TOOLS_SCHEMA
    + CONTEXT_TOOLS_SCHEMA
    + CLUSTER_LOGS_TOOLS_SCHEMA
    + TEMPO_TOOLS_SCHEMA
    + TRACE_LOGS_TOOLS_SCHEMA
    + PROM_TOOLS_SCHEMA
    + POSTGRES_TOOLS_SCHEMA
    + TEMPORAL_TOOLS_SCHEMA
    + K8SGPT_TOOLS_SCHEMA
    + CODE_TOOLS_SCHEMA
    + RUNBOOK_TOOLS_SCHEMA
)

_SCHEMA_BY_NAME = {s["function"]["name"]: s for s in ALL_TOOLS_SCHEMA}


def tools_for(names: list[str]) -> tuple[list, dict]:
    """Подмножество реестра по именам. Неизвестное имя — ошибка на старте, не в рантайме."""
    unknown = [n for n in names if n not in ALL_TOOLS_IMPL]
    if unknown:
        raise KeyError(f"unknown tools in prompt frontmatter: {unknown}")
    return [_SCHEMA_BY_NAME[n] for n in names], {n: ALL_TOOLS_IMPL[n] for n in names}
