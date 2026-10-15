"""Legacy k8sgpt CLI wrapper with explain enabled.

The workshop MCP integration lives in mcp_gateway.py/mcp_client.py, forbids explain
and restricts namespaces. Its policy does not apply to this legacy CLI wrapper.
When QAI_MCP_CONFIG selects MCP, investigator has no fallback to this tool.
"""

from __future__ import annotations

import os
import shutil
import subprocess

CONTEXT = os.getenv("KUBECTL_CONTEXT", "kind-qai-boutique")


def k8sgpt_analyze(namespace: str = "default") -> str:
    """Run k8sgpt analyze --explain against the Kind cluster."""
    if not shutil.which("k8sgpt"):
        return (
            "k8sgpt not found in PATH. Install: "
            "https://github.com/k8sgpt-ai/k8sgpt — "
            "brew install k8sgpt  OR download release binary. "
            "Then: k8sgpt auth add && k8sgpt analyze --explain"
        )
    cmd = [
        "k8sgpt",
        "analyze",
        "--explain",
        "--kubecontext",
        CONTEXT,
        "-n",
        namespace,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        output = (out.stdout or "") + (out.stderr or "")
        if out.returncode != 0:
            return f"k8sgpt_analyze failed: command exited with code {out.returncode}: {output.strip()}"
        # Keep the diagnostic intact. LLM context limits belong to the harness.
        return output or "(empty k8sgpt output)"
    except Exception as exc:
        return f"k8sgpt_analyze failed: {exc}"


K8SGPT_TOOLS_IMPL = {"k8sgpt_analyze": k8sgpt_analyze}
K8SGPT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "k8sgpt_analyze",
            "description": (
                "Diagnose Kubernetes startup, readiness and restart problems in a namespace via k8sgpt CLI. "
                "Use after identifying an unhealthy workload. Its LLM explanation is a hypothesis to verify "
                "against Kubernetes evidence; no findings does not exclude an application bug. Requires a configured AI backend."
            ),
            "parameters": {
                "type": "object",
                "properties": {"namespace": {"type": "string"}},
            },
        },
    }
]
