#!/usr/bin/env python3
"""Полное расследование одного или нескольких багов в подготовленном окружении.

  python e2e.py --read-only BUG-1024
  python e2e.py --read-only --mode workflow BUG-1024  # фиксированный baseline
  python e2e.py --read-only BUG-1024 BUG-TEMP-01 BUG-TEMP-02
  python e2e.py --read-only BUG-TEMP-01 BUG-TEMP-02  # fingerprint-группировка нескольких задач

Требования: стенд и исходные учебные события заранее подготовлены, API-профиль настроен.
Подготовка по docs/participant-prework-draft.md; эта команда сама учебные сбои не создаёт.
Вердикт → reports/<BUG-ID>.json, трейс прогона → reports/<BUG-ID>.trace.jsonl.
--read-only отключает learning, экспорт в Tempo и произвольный SQL роли;
локальные отчёты сохраняются, состояние стенда не меняется.
Exit: 0 — все отчёты приняты контрактом (включая обоснованный low),
1 — отказ контракта/ошибка выполнения или настройки, 2 — неверный вызов.
Exit 0 не доказывает семантическую правильность диагноза: нужен eval/ручная проверка.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("BOUTIQUE_ROOT", str(ROOT.parent / "microservices-demo"))
os.environ.setdefault("KUBECTL_CONTEXT", "kind-qai-boutique")

from agents.qai import REPORTS_DIR as REPORTS, run_investigation  # noqa: E402
from harness.fingerprint import group_failures  # noqa: E402
from harness.verdict import validate_verdict
from skills.tracker import tracker_get  # noqa: E402


def _first_line(report: str) -> str:
    return report.splitlines()[0].lstrip("# ").strip() if report else ""


def main(bug_ids: list[str]) -> int:
    if bug_ids in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    mode = "agent"
    if "--mode" in bug_ids:
        index = bug_ids.index("--mode")
        if index + 1 >= len(bug_ids) or bug_ids[index + 1] not in {"agent", "workflow"}:
            print("--mode requires agent or workflow", file=sys.stderr)
            return 2
        mode = bug_ids[index + 1]
        bug_ids = bug_ids[:index] + bug_ids[index + 2:]
    if "--read-only" in bug_ids:
        os.environ["QAI_READ_ONLY"] = "1"
        bug_ids = [bug_id for bug_id in bug_ids if bug_id != "--read-only"]
    if not bug_ids:
        print(__doc__)
        return 2
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing. Copy .env.example -> .env", file=sys.stderr)
        return 1
    REPORTS.mkdir(parents=True, exist_ok=True)

    # Группировка без LLM: одинаковые симптомы расследуем один раз.
    failures = [{"id": b, "component": "", "message": _first_line(tracker_get(b))} for b in bug_ids]
    groups = group_failures(failures)
    if len(groups) < len(bug_ids):
        print(f"fingerprint: {len(bug_ids)} репортов → {len(groups)} групп")

    exit_code = 0
    for members in groups.values():
        lead = members[0]["id"]
        result = run_investigation(lead, mode=mode)
        (REPORTS / f"{lead}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        errors = validate_verdict(result, expected_bug_id=lead)
        if errors:
            exit_code = 1
            print(f"Rejected verdict {lead}: " + "; ".join(errors), file=sys.stderr)
        for other in members[1:]:
            (REPORTS / f"{other['id']}.json").write_text(
                json.dumps({"bug_id": other["id"], "same_as": lead}, ensure_ascii=False), encoding="utf-8"
            )
        print(f"\n→ {REPORTS.name}/{lead}.json  confidence={result.get('confidence')}  "
              f"trace_id={result.get('run', {}).get('trace_id')}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
