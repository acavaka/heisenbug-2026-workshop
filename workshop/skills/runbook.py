"""Skill: обратная связь в знания. Агент дописывает подтверждённый паттерн в runbook.

Паттерн из промышленных систем диагностики: после вердикта с высокой уверенностью
строка «симптом → первый скилл → виновник» попадает в runbook-map, и следующий
прогон (report-analyzer читает wiki_get) начинает с проверенного направления.

Запись вызывает runtime agents/qai.py после принятого application-вердикта high,
если read-only выключен. Решение о диагнозе принимает модель; допуск записи проверяет код.
LLM-ролям инструмент записи не выдаётся. Это внешняя память, не обучение весов модели.
Каждая строка помечена [AI YYYY-MM-DD], чтобы отличать от написанного людьми.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path

RUNBOOK = Path(__file__).resolve().parents[2] / "fixtures" / "wiki" / "runbook-map.md"
SECTION = "## Learned patterns [AI]"
HEADER = "| Date | Symptom | First skill | Culprit | Tracker |\n|---|---|---|---|---|"


def runbook_append(symptom: str, first_skill: str, culprit: str, bug_id: str) -> str:
    """Добавить строку в секцию Learned patterns. Дубликат по bug_id не добавляется."""
    if os.getenv("QAI_READ_ONLY") == "1":
        return "TOOL ERROR: runbook_append is disabled in read-only mode"
    text = RUNBOOK.read_text(encoding="utf-8") if RUNBOOK.exists() else "# Runbook map\n"
    row = f"| [AI {date.today().isoformat()}] | {symptom} | {first_skill} | {culprit} | {bug_id} |"
    if SECTION not in text:
        text = text.rstrip() + f"\n\n{SECTION}\n\n{HEADER}\n"
    head, _, tail = text.partition(SECTION)
    if f"| {bug_id} |" in tail:
        return f"runbook: паттерн для {bug_id} уже есть, не дублирую"
    text = head + SECTION + tail.rstrip() + "\n" + row + "\n"
    RUNBOOK.write_text(text, encoding="utf-8")
    return f"runbook: добавлено → {row}"


RUNBOOK_TOOLS_IMPL = {"runbook_append": runbook_append}
RUNBOOK_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "runbook_append",
            "description": (
                "Записать подтверждённый паттерн (симптом → первый скилл → виновник) в runbook-map. "
                "Только после вердикта с confidence=high и только оркестратором."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string"},
                    "first_skill": {"type": "string"},
                    "culprit": {"type": "string", "description": "файл:строка"},
                    "bug_id": {"type": "string"},
                },
                "required": ["symptom", "first_skill", "culprit", "bug_id"],
            },
        },
    }
]


if __name__ == "__main__":
    import tempfile

    RUNBOOK = Path(tempfile.mkdtemp()) / "runbook-map.md"
    RUNBOOK.write_text("# Runbook\n\n| Symptom | First skill |\n|---|---|\n| a | b |\n", encoding="utf-8")
    print(runbook_append("PDP price ≠ cart", "grep_pod_logs productcatalogservice", "product_catalog.go:31", "BUG-1024"))
    print(runbook_append("PDP price ≠ cart", "grep_pod_logs", "x", "BUG-1024"))
    t = RUNBOOK.read_text(encoding="utf-8")
    assert t.count("BUG-1024") == 1 and SECTION in t and "| a | b |" in t, t
    print("runbook OK")
