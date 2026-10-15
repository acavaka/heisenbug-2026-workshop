"""Skills: Prometheus instant queries."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

PROM_URL = os.getenv("PROM_URL", "http://127.0.0.1:9090")


def prom_query(query: str) -> str:
    """Run a Prometheus instant query (PromQL)."""
    url = (
        PROM_URL.rstrip("/")
        + "/api/v1/query?"
        + urllib.parse.urlencode({"query": query})
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        json.loads(raw)
        return raw
    except Exception as exc:
        return f"Prometheus query failed: {exc}"


PROM_TOOLS_IMPL = {"prom_query": prom_query}
PROM_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "prom_query",
            "description": "Query current Prometheus metrics with PromQL. Empty results mean no matching samples, not a healthy system. This tool does not query an incident's historical time range.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]
