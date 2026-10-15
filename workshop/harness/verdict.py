"""Offline verdict contract and citation checks shared by runtime and eval.

These checks establish shape and provenance, not the semantic truth of a diagnosis.
Tool observations must come from execution, never from a model-authored summary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CODE_TOOLS = {"read_file", "code_search"}
STAND_TOOLS = {
    "kubectl_get_pods", "kubectl_logs", "grep_pod_logs", "tempo_search",
    "tempo_get_trace", "trace_to_logs", "prom_query", "postgres_query", "temporal_inspect",
}
TOOL_ERRORS = {
    "kubectl_get_pods": ("kubectl failed",),
    "kubectl_logs": ("kubectl failed",),
    "grep_pod_logs": ("kubectl failed", "Invalid regex:", "No matches for"),
    "tempo_search": ("Tempo request failed",),
    "tempo_get_trace": ("Tempo request failed", "Tempo returned invalid JSON"),
    "trace_to_logs": ("NOT IMPLEMENTED:", "Tempo request failed", "Tempo returned invalid JSON", "trace_to_logs: не смог"),
    "prom_query": ("Prometheus query failed:",),
    "postgres_query": ("postgres_query failed:", "Only read-only", "Query must start", "ERROR:", "FATAL:", "psql:"),
    "temporal_inspect": ("temporal_inspect failed:", "temporalio not installed."),
    "read_file": ("File not found:", "Path escapes", "Source path must be relative:", "Unknown source root:", "Only the order-worker", "Path does not belong"),
    "code_search": ("Invalid regex:", "Invalid glob:", "Unknown source root:", "Source roots not found:", "No matches for"),
    "k8sgpt_analyze": ("k8sgpt not found in PATH.", "k8sgpt_analyze failed:"),
}


def tool_result_failed(tool: str, result: str) -> bool:
    """Recognize tool diagnostics without mistaking application ERROR logs for them."""
    text = result.lstrip()
    if text.startswith(("TOOL ERROR:", "ERROR: unknown tool ")):
        return True
    if text.startswith(TOOL_ERRORS.get(tool, ())):
        return True
    if tool in {"prom_query", "tempo_search", "tempo_get_trace"}:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return False
        return isinstance(payload, dict) and payload.get("status") == "error"
    return False


def _normal(text: str) -> str:
    return " ".join(text.split())


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def _observations(result: dict) -> list[dict]:
    values = result.get("tool_observations", [])
    if not isinstance(values, list):
        return []
    return [
        obs for obs in values
        if isinstance(obs, dict) and isinstance(obs.get("tool"), str)
        and isinstance(obs.get("args"), dict) and isinstance(obs.get("result"), str)
        and obs.get("status") != "error" and not tool_result_failed(obs["tool"], obs["result"])
    ]


def _code_path(path: str, root: str | None = None) -> Path:
    from skills.code import resolve_code_path

    return resolve_code_path(path, root=root)


def _supports_line(observation: dict, file: Path, number: int, quote: str) -> bool:
    """Bind a quoted code observation to the cited file and exact source line."""
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
        line = lines[number - 1].strip()
    except (OSError, UnicodeError, IndexError):
        return False
    if not line or not (_normal(quote) in _normal(line) or _normal(line) in _normal(quote)):
        return False
    if observation["tool"] == "read_file":
        args = observation["args"]
        path = args.get("path")
        if not isinstance(path, str):
            return False
        try:
            if _code_path(path, args.get("root")) != file:
                return False
        except (ValueError, TypeError):
            return False
        for match in re.finditer(rf"^\s*{number}:\s*(.*)$", observation["result"], re.MULTILINE):
            if _normal(match.group(1)) == _normal(line):
                return True
        return False
    if observation["tool"] == "code_search":
        for row in observation["result"].splitlines():
            match = re.match(r"(.+):(\d+):\s*(.*)$", row)
            if not match or int(match.group(2)) != number or _normal(match.group(3)) != _normal(line):
                continue
            try:
                if _code_path(match.group(1)) == file:
                    return True
            except (ValueError, TypeError):
                continue
    return False


def validate_verdict(result: object, *, expected_bug_id: str | None = None) -> list[str]:
    """Return all validation errors. Does not call LLM, tools, or external services."""
    if not isinstance(result, dict):
        return ["verdict must be a JSON object"]
    errors: list[str] = []
    if result.get("validation_errors"):
        errors.append("verdict already contains validation_errors")
    for field in ("bug_id", "root_cause", "fix_direction"):
        if not isinstance(result.get(field), str):
            errors.append(f"{field} must be a string")
    if isinstance(result.get("bug_id"), str) and not result["bug_id"].strip():
        errors.append("bug_id must not be empty")
    if expected_bug_id is not None and result.get("bug_id") != expected_bug_id:
        errors.append("bug_id does not match requested case")
    confidence = result.get("confidence")
    profile = result.get("investigation_type", "application")
    if profile not in ("application", "infrastructure"):
        errors.append("investigation_type must be application or infrastructure")
    if confidence not in ("low", "medium", "high"):
        errors.append("confidence must be low, medium, or high")
    for field in ("culprit_files", "reasons", "false_leads", "red_team", "limitations"):
        if not _strings(result.get(field)):
            errors.append(f"{field} must be a list of nonempty strings")
    if _strings(result.get("reasons")) and not result["reasons"]:
        errors.append("reasons must not be empty")
    if _strings(result.get("red_team")) and len(result["red_team"]) != 3:
        errors.append("red_team must contain three answers")
    if confidence == "low" and not result.get("limitations"):
        errors.append("low confidence must explain missing data in limitations")
    if confidence in ("medium", "high"):
        if not isinstance(result.get("root_cause"), str) or not result["root_cause"].strip():
            errors.append("a diagnosis requires a nonempty root_cause")
        if not isinstance(result.get("fix_direction"), str) or not result["fix_direction"].strip():
            errors.append("a diagnosis requires a nonempty fix_direction")
    observations = _observations(result)
    if "tool_observations" in result and not isinstance(result["tool_observations"], list):
        errors.append("tool_observations must be a list")
    evidence = result.get("evidence")
    grounded: list[tuple[dict, dict]] = []
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []
    for index, entry in enumerate(evidence):
        label = f"evidence[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        if not isinstance(entry.get("claim"), str) or not entry["claim"].strip():
            errors.append(f"{label}.claim must be a nonempty string")
        if entry.get("kind") not in ("ФАКТ", "ВЫВОД", "ГИПОТЕЗА"):
            errors.append(f"{label}.kind is invalid")
        if not isinstance(entry.get("source"), str):
            errors.append(f"{label}.source must be a string")
        if entry.get("kind") != "ФАКТ":
            continue
        quote, source = entry.get("quote"), entry.get("source")
        if not isinstance(quote, str) or not quote.strip():
            errors.append(f"{label}: a fact requires a nonempty quote")
            continue
        matches = [obs for obs in observations if obs["tool"] == source and _normal(quote) in _normal(obs["result"])]
        if not matches:
            errors.append(f"{label}: quote is not present in an observed {source} result")
        grounded.extend((entry, obs) for obs in matches)
    code = [(entry, obs) for entry, obs in grounded if obs["tool"] in CODE_TOOLS]
    stand = [(entry, obs) for entry, obs in grounded if obs["tool"] in STAND_TOOLS]
    if profile == "infrastructure":
        from harness.infra_verdict import validate_infrastructure
        errors.extend(validate_infrastructure(result, grounded))
    elif confidence == "high":
        if not code or not stand:
            errors.append("high confidence requires grounded code and stand facts")
        if not result.get("culprit_files"):
            errors.append("high confidence requires culprit_files")
    elif confidence == "medium" and not (code or stand):
        errors.append("medium confidence requires at least one grounded code or stand fact")
    if _strings(result.get("culprit_files")):
        for citation in result["culprit_files"]:
            match = re.fullmatch(r"(.+):([1-9]\d*)", citation)
            if not match:
                errors.append(f"invalid file:line citation: {citation}")
                continue
            path, line = match.group(1), int(match.group(2))
            try:
                file = _code_path(path)
                count = len(file.read_text(encoding="utf-8").splitlines())
            except (ValueError, TypeError, OSError, UnicodeError):
                errors.append(f"citation is outside code roots or unavailable: {citation}")
                continue
            if line > count:
                errors.append(f"citation line does not exist: {citation}")
                continue
            if not any(_supports_line(obs, file, line, entry["quote"]) for entry, obs in code):
                errors.append(f"citation is not supported by observed code: {citation}")
    return errors


def invalid_verdict(bug_id: str, errors: list[str]) -> dict:
    """A controlled failure can be reported but must never pass eval or learn."""
    return {
        "bug_id": bug_id,
        "root_cause": "",
        "culprit_files": [],
        "confidence": "low",
        "reasons": ["Ответ модели не прошёл проверку контракта или доказательств."],
        "evidence": [],
        "false_leads": [],
        "red_team": ["Причина не подтверждена.", "Доказательства не прошли проверку.", "Требуется повторное расследование."],
        "limitations": errors,
        "fix_direction": "",
        "validation_errors": errors,
    }
