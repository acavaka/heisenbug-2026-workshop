"""Skills: kubectl logs / pods against Kind Boutique cluster."""

from __future__ import annotations

import os
import re
import subprocess

CONTEXT = os.getenv("KUBECTL_CONTEXT", "kind-qai-boutique")
NAMESPACE = os.getenv("BOUTIQUE_NAMESPACE", "default")
MAX_LINES = int(os.getenv("KUBECTL_LOG_MAX_LINES", "80"))


def _kubectl(args: list[str]) -> str:
    cmd = ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "kubectl failed: kubectl not found in PATH"
    except subprocess.TimeoutExpired:
        return "kubectl failed: timed out after 30 seconds"
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return f"kubectl failed ({proc.returncode}): {out.strip()}"
    return out.strip()


def kubectl_get_pods() -> str:
    """List pods in the Boutique namespace."""
    return _kubectl(["get", "pods", "-o", "wide"])


def kubectl_logs(deployment: str, tail: int = 100) -> str:
    """Fetch recent logs from a deployment (e.g. productcatalogservice)."""
    tail = max(1, min(int(tail), 500))
    return _kubectl(["logs", f"deploy/{deployment}", f"--tail={tail}"])


def grep_pod_logs(deployment: str, pattern: str, tail: int = 300) -> str:
    """Fetch logs and filter lines matching a regex (case-insensitive)."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"Invalid regex: {exc}"
    tail = max(1, min(int(tail), 500))
    raw = kubectl_logs(deployment, tail=tail)
    if raw.startswith("kubectl failed"):
        return raw
    matches = []
    for line in raw.splitlines():
        if rx.search(line):
            matches.append(line)
            if len(matches) >= MAX_LINES:
                break
    if not matches:
        return f"No matches for {pattern!r} in deploy/{deployment} (last {tail} lines)"
    extra = ""
    if len(matches) >= MAX_LINES:
        extra = f"\n... showing first {MAX_LINES} matches"
    return "\n".join(matches) + extra


CLUSTER_LOGS_TOOLS_IMPL = {
    "kubectl_get_pods": kubectl_get_pods,
    "kubectl_logs": kubectl_logs,
    "grep_pod_logs": grep_pod_logs,
}

CLUSTER_LOGS_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "kubectl_get_pods",
            "description": "List current pods and readiness in the configured namespace. Use for startup/restart symptoms; healthy pods do not prove business operations work.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kubectl_logs",
            "description": (
                "Get a bounded recent log sample from a Boutique deployment (at most 500 lines; not complete incident history). "
                "Useful deployments: productcatalogservice, frontend, cartservice, checkoutservice, paymentservice."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deployment": {
                        "type": "string",
                        "description": "Deployment name, e.g. productcatalogservice",
                    },
                    "tail": {
                        "type": "integer",
                        "description": "How many log lines from the end (default 100)",
                    },
                },
                "required": ["deployment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_pod_logs",
            "description": (
                "Search a recent deployment log sample with a regex using an observed id or message. "
                "No matches applies only to this sample; it does not prove the event never happened."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deployment": {"type": "string"},
                    "pattern": {"type": "string"},
                    "tail": {"type": "integer"},
                },
                "required": ["deployment", "pattern"],
            },
        },
    },
]
