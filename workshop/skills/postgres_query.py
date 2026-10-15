"""Legacy SQL wrapper with SELECT/WITH filtering, using an administrative DB role.

Disabled in QAI_READ_ONLY: a text filter is not a read-only database permission.
A production read path needs a restricted DB role and a bounded query tool.
"""

from __future__ import annotations

import os
import re
import subprocess

CONTEXT = os.getenv("KUBECTL_CONTEXT", "kind-qai-boutique")
NAMESPACE = os.getenv("BOUTIQUE_NAMESPACE", "default")

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b",
    re.I,
)


def postgres_query(sql: str) -> str:
    """Run a filtered legacy query; reject calls in the strict read-only profile."""
    if os.getenv("QAI_READ_ONLY") == "1":
        return "TOOL ERROR: arbitrary postgres_query is disabled in read-only mode; a restricted DB role is required"
    sql = sql.strip().rstrip(";")
    if _FORBIDDEN.search(sql):
        return "Only read-only SELECT/WITH queries are allowed."
    if not re.match(r"^(select|with)\b", sql, re.I):
        return "Query must start with SELECT or WITH."
    cmd = [
        "kubectl",
        "--context",
        CONTEXT,
        "-n",
        NAMESPACE,
        "exec",
        "deploy/postgres",
        "--",
        "psql",
        "-U",
        "postgres",
        "-d",
        "orders",
        "-c",
        sql,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        output = (out.stdout or "") + (out.stderr or "")
        if out.returncode != 0:
            return f"postgres_query failed: command exited with code {out.returncode}: {output.strip()}"
        return output
    except Exception as exc:
        return f"postgres_query failed: {exc}"


POSTGRES_TOOLS_IMPL = {"postgres_query": postgres_query}
POSTGRES_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "postgres_query",
            "description": "Query workshop orders/payments using SELECT/WITH. The legacy connection uses an admin DB role: keyword filtering is not a read-only guarantee. Disabled in strict read-only mode.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    }
]
