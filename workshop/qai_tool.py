#!/usr/bin/env python3
"""CLI-диспетчер скиллов: тот же реестр, что у DIY-харнесса, но для Claude Code / Codex / Cursor.

Принцип «скрипты собирают факты, LLM рассуждает»: агент любого хоста вызывает
скилл как команду и получает текст. Логика скилла одна, в skills/*.py.

  python qai_tool.py --list
  python qai_tool.py --read-only tracker_get bug_id=BUG-1024
  python qai_tool.py tracker_get bug_id=BUG-1024
  python qai_tool.py grep_pod_logs deployment=productcatalogservice pattern="cache (hit|miss)"
  python qai_tool.py trace_to_logs trace_id=<hex> extra_keys='["ORD-1"]'
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402, F401 — utf-8 stdout на Windows
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

from skills import ALL_TOOLS_IMPL, ALL_TOOLS_SCHEMA  # noqa: E402
from harness.tool_result import ToolResult
from harness.verdict import tool_result_failed  # noqa: E402

_PARAMETERS = {s["function"]["name"]: s["function"]["parameters"].get("properties", {}) for s in ALL_TOOLS_SCHEMA}


def _coerce(value: str, schema: dict):
    # Identifiers, regexes and queries remain strings even when they look like JSON.
    if schema.get("type") == "string":
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--read-only":
        os.environ["QAI_READ_ONLY"] = "1"
        argv = argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if argv[0] == "--list":
        for s in ALL_TOOLS_SCHEMA:
            fn = s["function"]
            if os.getenv("QAI_READ_ONLY") == "1" and fn["name"] in {"postgres_query", "runbook_append"}:
                continue
            params = ", ".join(fn["parameters"].get("properties", {}))
            print(f"{fn['name']}({params})\n    {fn['description']}")
        return 0
    name, *pairs = argv
    if name not in ALL_TOOLS_IMPL:
        print(f"unknown tool {name}. See --list", file=sys.stderr)
        return 2
    kwargs = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            print(f"bad argument {pair!r}, expected key=value", file=sys.stderr)
            return 2
        if key in kwargs or key not in _PARAMETERS[name]:
            print(f"TOOL ERROR: unknown or duplicate argument {key!r}", file=sys.stderr)
            return 2
        kwargs[key] = _coerce(value, _PARAMETERS[name][key])
    protocol_error = False
    try:
        value = ALL_TOOLS_IMPL[name](**kwargs)
        protocol_error = isinstance(value, ToolResult) and value.is_error
        result = str(value)
    except Exception as exc:
        result = f"TOOL ERROR: {exc}"
    print(result)
    return 1 if protocol_error or tool_result_failed(name, result) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
