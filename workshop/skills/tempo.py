"""Skills: Grafana Tempo trace search/fetch."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

TEMPO_URL = os.getenv("TEMPO_URL", "http://127.0.0.1:3200")


def _get(path: str, params: dict | None = None) -> str:
    url = TEMPO_URL.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return f"Tempo request failed: {exc}. Is ports-workshop.sh running?"


def tempo_search(query: str = "{}", limit: int = 10) -> str:
    """Search traces. query is Tempo TraceQL or empty '{}' for recent."""
    return _get("/api/search", {"q": query, "limit": str(limit)})


def tempo_get_trace(trace_id: str) -> str:
    """Fetch a full trace by hex trace id."""
    raw = _get(f"/api/traces/{trace_id}")
    if raw.startswith("Tempo request failed"):
        return raw
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"Tempo returned invalid JSON for trace {trace_id}: {exc}"
    # Preserve the full document for JSON consumers; the harness limits LLM text.
    return raw


TEMPO_TOOLS_IMPL = {
    "tempo_search": tempo_search,
    "tempo_get_trace": tempo_get_trace,
}

TEMPO_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "tempo_search",
            "description": "Search recent traces in Grafana Tempo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "TraceQL or '{}' for recent traces",
                    },
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tempo_get_trace",
            "description": "Get full Tempo trace by trace id.",
            "parameters": {
                "type": "object",
                "properties": {"trace_id": {"type": "string"}},
                "required": ["trace_id"],
            },
        },
    },
]
