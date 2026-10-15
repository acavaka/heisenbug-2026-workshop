#!/usr/bin/env python3
"""Рендер адаптеров: prompts/*.md → Claude Code, Codex, Cursor (единый источник промптов).

Единый источник: workshop/prompts/*.md + AGENTS.md. Генерируется (в корне репо):
  .claude/agents/qai-*.md          субагенты Claude Code (read-only CLI и общие MCP-каталоги)
  .claude/skills/qai/SKILL.md      /qai <BUG-ID> в Claude Code
  .agents/skills/qai/SKILL.md      тот же skill для Codex CLI и Cursor
  .cursor/rules/qai.mdc            «читай AGENTS.md»
  CLAUDE.md                        копия AGENTS.md

Запуск: python render.py   (из workshop/). Проверка без записи: python render.py --check
Ручные правки сгенерированных файлов перезаписываются: правь prompts/ и AGENTS.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness.prompts import list_roles, load_prompt  # noqa: E402
from skills import ALL_TOOLS_SCHEMA  # noqa: E402

WS = Path(__file__).resolve().parent
ROOT = WS.parent
MARK = "<!-- GENERATED from workshop/prompts by workshop/render.py. Do not edit. -->"
TOOL_CMD = "python workshop/qai_tool.py --read-only"
READ_ONLY_EXCLUDED = {"postgres_query", "runbook_append"}


def tool_catalog(names: list[str] | None = None) -> str:
    rows = []
    for s in ALL_TOOLS_SCHEMA:
        fn = s["function"]
        if fn["name"] in READ_ONLY_EXCLUDED or (names is not None and fn["name"] not in names):
            continue
        params = " ".join(f"{p}=<{p}>" for p in fn["parameters"].get("properties", {}))
        rows.append(f"- `{TOOL_CMD} {fn['name']} {params}`\n  {fn['description']}")
    return "\n".join(rows)


ORCHESTRATOR = "qai-orchestrator"
WORKERS = [r for r in list_roles() if r != ORCHESTRATOR]


def claude_agent(role: str) -> str:
    """Субагент Claude Code для роли; оркестратор — основная сессия через /qai."""
    p = load_prompt(role)
    # Tool names in frontmatter; command permissions are a separate host setting.
    # Bash itself is not a sandbox or per-role tool allowlist.
    tools = "Bash, mcp__k8sgpt__*" if role == "qai-data-investigator" else ("Bash, mcp__k8sgpt__qai_catalog, mcp__k8sgpt__qai_evidence_get" if role == "qai-hypothesis-checker" else "Bash")
    # Application observations (including report/code reads) must enter the same runtime catalogue.
    tools += ", mcp__qai_application__qai_observe, mcp__qai_application__qai_catalog, mcp__qai_application__qai_evidence_get"
    return (
        f"---\nname: {p.name}\ndescription: {p.description}\ntools: {tools}\n---\n{MARK}\n\n"
        f"{p.body}\n\n## Доступные скиллы (вызывать через Bash)\n{tool_catalog(p.tools)}\n"
        "\nДля application с подключённым MCP qai_application собирай первичные наблюдения через "
        "qai_observe этого сервера с investigation_id оркестратора; разрешены только инструменты твоей роли. "
        "Читай каталог через qai_catalog/qai_evidence_get. Не создавай отдельное расследование и не выноси финальный вердикт. "
        "Без application MCP используй перечисленные read-only команды; их ответы автоматически в каталог не входят. "
        "Investigator также может использовать MCP k8sgpt по правилам роли. Не читай исходники/данные через "
        "cat, Read, Grep или inline-код в обход инструментов. При недоступной команде укажи limitation.\n"
        "Это правило поведения: доступ к Bash сам по себе не обеспечивает изоляцию файлов и команд.\n"
    )


def skill_md() -> str:
    orch = load_prompt(ORCHESTRATOR)
    return f"""---
name: qai
description: {orch.description} Invoke for '/qai <BUG-ID>' (BUG-1024, BUG-TEMP-01, ...).
disable-model-invocation: true
---
{MARK}

# /qai <BUG-ID>

Эта сессия и есть оркестратор. Промпт роли ниже, правила в AGENTS.md.

{orch.body}

## Как делегировать

- Claude Code: роли-исполнители — субагенты `.claude/agents/qai-*.md`; вызывай `Agent(subagent_type=<роль>)`
  по выбранному вопросу, передавая накопленные данные и ссылки. Сам инструменты стенда не вызывай.
- Codex / Cursor: используй доступное делегирование; без субагентов выполни выбранную роль сам, соблюдая набор скиллов
  каждой роли (см. `.claude/agents/qai-*.md` как спецификацию) и правила доказательности.
- Investigator также может использовать подключённый MCP k8sgpt (docs/k8sgpt-mcp.md).
  В replay не запрашивай живые источники.
- Во всех ролях используй read-only команды ниже. Произвольный postgres_query отключён;
  отсутствие сведений БД отрази в limitations. Не обходи ограничения через shell или другие tools.
- Для infrastructure используй MCP qai_begin → qai_observe → qai_catalog/qai_evidence_get → qai_validate.
  Передай investigation_id между ролями. Только valid=true подтверждает проверку полного verdict.
  Прямые диагностические вызовы k8sgpt вне qai_observe в каталог не входят.
- Для application используй MCP qai_application по docs/application-mcp.md: qai_begin → qai_observe →
  qai_catalog/qai_evidence_get → qai_validate. Все роли используют один investigation_id одного сервера.
  Передавай evidence_ref из его каталога и culprit_files из observed_file_lines; source/quote раскрывает runtime.
  Только фактический valid=true означает принятие. CLI-ответы в этот каталог автоматически не входят.
  Без подключённого application MCP не заявляй автоматическую валидацию или принятие вердикта.
- Ролевые ограничения в редакторах остаются инструкциями, а не отдельной песочницей;
  не заявляй иных гарантий. Не смешивай application/infrastructure-серверы и ссылки.
- Не записывай runbook из редактора по самооценке confidence=high. Сначала нужен проверенный
  отчёт с независимо сохранёнными наблюдениями и отдельный разрешённый этап записи.

## Скиллы (только как команды, без inline-кода)
{tool_catalog()}

Запускай команды из корня репозитория с активированным workshop/.venv.
Переменные окружения: workshop/.env (KUBECTL_CONTEXT, TEMPO_URL, BOUTIQUE_ROOT, ORDER_WORKER_ROOT).
"""


def cursor_rule() -> str:
    return f"""---
description: QAI workshop agent rules
alwaysApply: true
---
{MARK}
Read and follow AGENTS.md. Skills live in .agents/skills/qai/SKILL.md and are invoked as `{TOOL_CMD} <tool> key=value`.
For validated application investigations use MCP qai_application (docs/application-mcp.md); for infrastructure use MCP k8sgpt (docs/k8sgpt-mcp.md).
Collect observations through qai_observe and submit via qai_validate of the same server and investigation_id; only an actual valid=true means acceptance. CLI output is not automatically registered evidence.
"""


def outputs() -> dict[Path, str]:
    files = {ROOT / ".claude" / "agents" / f"{r}.md": claude_agent(r) for r in WORKERS}
    files[ROOT / ".claude" / "skills" / "qai" / "SKILL.md"] = skill_md()
    files[ROOT / ".agents" / "skills" / "qai" / "SKILL.md"] = skill_md()
    files[ROOT / ".cursor" / "rules" / "qai.mdc"] = cursor_rule()
    files[ROOT / "CLAUDE.md"] = f"{MARK}\n" + (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    return files


def main(check: bool) -> int:
    stale = []
    wanted = outputs()
    # Устаревшие сгенерированные файлы (есть MARK, но их больше не рендерим) удаляем.
    for old in list((ROOT / ".claude" / "agents").glob("qai-*.md")):
        if old not in wanted and MARK in old.read_text(encoding="utf-8"):
            stale.append(old)
            if not check:
                old.unlink()
    for path, content in wanted.items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        stale.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    for p in stale:
        print(("stale: " if check else "written: ") + str(p.relative_to(ROOT)))
    if not stale:
        print("adapters up to date")
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
