"""Skills: inspect Temporal workflows via Python client (localhost:7233)."""

from __future__ import annotations

import asyncio
import json
import os

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "127.0.0.1:7233")


async def _describe(workflow_id: str) -> str:
    try:
        from temporalio.client import Client
    except ImportError:
        return "temporalio not installed. pip install temporalio"

    try:
        client = await Client.connect(TEMPORAL_HOST)
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        payload = {
            "workflow_id": desc.id,
            "run_id": desc.run_id,
            "status": str(desc.status),
            "workflow_type": desc.workflow_type,
            "start_time": str(desc.start_time),
            "execution_time": str(getattr(desc, "execution_time", "")),
        }
        return json.dumps(payload, indent=2, default=str)
    except Exception as exc:
        return f"temporal_inspect failed: {exc}. Is Temporal port-forward :7233 up?"


def temporal_inspect(workflow_id: str) -> str:
    """Describe a Temporal workflow by id (see Temporal UI)."""
    return asyncio.run(_describe(workflow_id))


TEMPORAL_TOOLS_IMPL = {"temporal_inspect": temporal_inspect}
TEMPORAL_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "temporal_inspect",
            "description": "Describe the current/latest Temporal execution by workflow_id (status, run_id, times). Does not return event history, retry attempts or proof of payment/refund; correlate with other sources.",
            "parameters": {
                "type": "object",
                "properties": {"workflow_id": {"type": "string"}},
                "required": ["workflow_id"],
            },
        },
    }
]
