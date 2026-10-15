"""Read-only Temporal visibility, describe and event history, shared by CLI/MCP.

Namespace is deployment configuration, not a model-selected argument. Each call
reads one page with bounded time and JSON size; no workflow mutations or queries
that execute workflow code are exposed.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from uuid import UUID

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TOTAL_TIMEOUT_S = 20
RPC_TIMEOUT = timedelta(seconds=10)
MAX_RESPONSE_BYTES = 120_000
MAX_CURSOR_CHARS = 16_384


def _text(value, name, maximum=1000, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        raise ValueError(f"{name} must be a {'possibly empty ' if allow_empty else 'nonempty '}string <= {maximum} characters")
    return value


def _run_id(value, optional=False):
    if optional and value is None:
        return None
    _text(value, "run_id", 36)
    if str(UUID(value)) != value.lower():
        raise ValueError("run_id must be a UUID copied from an observed execution")
    return value


def _cursor(token, scope):
    _text(token, "page_token", MAX_CURSOR_CHARS, allow_empty=True)
    if not token:
        return None
    try:
        value = json.loads(base64.b64decode(token, validate=True))
        if value["v"] != 1 or value["scope"] != scope:
            raise ValueError("page_token belongs to another query, namespace or execution")
        return base64.b64decode(value["token"], validate=True)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid page_token: {exc}") from exc


def _next_cursor(token, scope):
    if not token:
        return ""
    data = {"v":1, "scope":scope, "token":base64.b64encode(token).decode("ascii")}
    result = base64.b64encode(json.dumps(data).encode()).decode("ascii")
    if len(result) > MAX_CURSOR_CHARS:
        raise ValueError("server continuation token exceeds cursor limit")
    return result


def _execution(desc):
    return {
        "workflow_id":desc.id, "run_id":desc.run_id,
        "status":getattr(desc.status, "name", str(desc.status)),
        "workflow_type":desc.workflow_type,
        **{name:str(getattr(desc, name, "") or "") for name in ("start_time", "execution_time", "close_time")},
    }


async def _read(operation, workflow_id=None, run_id=None, query="", page_size=20, page_token=""):
    from temporalio.client import Client

    _text(TEMPORAL_NAMESPACE, "TEMPORAL_NAMESPACE")
    if operation != "list":
        _text(workflow_id, "workflow_id")
        _run_id(run_id, optional=operation == "describe")
    _text(query, "query", 2000, allow_empty=True)
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
        raise ValueError("page_size must be an integer between 1 and 100")
    scope = {"operation":operation, "namespace":TEMPORAL_NAMESPACE,
             "query":query, "workflow_id":workflow_id, "run_id":run_id}
    token = _cursor(page_token, scope)
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    result = {"namespace":TEMPORAL_NAMESPACE, "observed_at":datetime.now(timezone.utc).isoformat()}
    if operation == "describe":
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        desc = await handle.describe(rpc_timeout=RPC_TIMEOUT)
        return {**result, **_execution(desc)}
    if operation == "list":
        page = client.list_workflows(query=query, page_size=page_size,
                                     next_page_token=token, rpc_timeout=RPC_TIMEOUT)
        await page.fetch_next_page()
        result.update(query=query, workflows=[_execution(row) for row in page.current_page],
                      limitations=["Visibility is eventually consistent. One page is not a complete search; absence does not prove no execution."])
    else:
        from google.protobuf.json_format import MessageToDict
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        page = handle.fetch_history_events(page_size=page_size, next_page_token=token,
                                          wait_new_event=False, rpc_timeout=RPC_TIMEOUT)
        await page.fetch_next_page()
        result.update(workflow_id=workflow_id, run_id=run_id,
                      events=[MessageToDict(event) for event in page.current_page],
                      limitations=["History may aggregate activity retry attempts; events do not independently prove external payment/refund effects.",
                                   "This is one observed page. Running executions may gain events after this read; an empty page does not prove absence of an action."])
    result.update(requested_page_size=page_size, continued=bool(page_token),
                  has_more=bool(page.next_page_token), next_page_token=_next_cursor(page.next_page_token, scope))
    return result


def _call(operation, **arguments):
    async def bounded():
        async with asyncio.timeout(TOTAL_TIMEOUT_S):
            return await _read(operation, **arguments)
    try:
        result = json.dumps(asyncio.run(bounded()), ensure_ascii=False, indent=2)
        if len(result.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise ValueError("response exceeds 120000 bytes; retry with smaller page_size or narrower query. No page accepted.")
        return result
    except Exception as exc:
        # Uniform error prefix keeps failures out of evidence in CLI, Python and MCP.
        return f"TOOL ERROR: Temporal {operation}: {type(exc).__name__}: {str(exc)[:2000]}"


def temporal_inspect(workflow_id: str, run_id: str | None = None) -> str:
    """Describe a pinned execution, or latest when run_id is omitted."""
    return _call("describe", workflow_id=workflow_id, run_id=run_id)


def temporal_list_workflows(query: str = "", page_size: int = 20, page_token: str = "") -> str:
    """Read one visibility page; query is Temporal visibility syntax, not SQL execution."""
    return _call("list", query=query, page_size=page_size, page_token=page_token)


def temporal_history(workflow_id: str, run_id: str, page_size: int = 20, page_token: str = "") -> str:
    """Read one event page of exactly this run, never long-poll for new events."""
    return _call("history", workflow_id=workflow_id, run_id=run_id, page_size=page_size, page_token=page_token)


_PAGE = {
    "page_size":{"type":"integer", "minimum":1, "maximum":100,
                 "description":"Requested server page size, default 20. Server may return a larger batch; total response is capped at 120000 bytes."},
    "page_token":{"type":"string", "maxLength":MAX_CURSOR_CHARS,
                  "description":"Opaque next_page_token from the same query/namespace/workflow/run; omit for first page."},
}
_ID = {"type":"string", "minLength":1, "maxLength":1000}
_RUN = {"type":"string", "minLength":36, "maxLength":36,
        "description":"Exact run_id UUID from list/describe; never invent it."}


def _schema(name, description, properties, required):
    return {"type":"function", "function":{"name":name, "description":description,
        "parameters":{"type":"object", "properties":properties, "required":required, "additionalProperties":False}}}


TEMPORAL_TOOLS_IMPL = {"temporal_inspect":temporal_inspect,
                       "temporal_list_workflows":temporal_list_workflows,
                       "temporal_history":temporal_history}
TEMPORAL_TOOLS_SCHEMA = [
    _schema("temporal_inspect", "Read-only describe of Temporal execution. Omit run_id for latest, then pin returned run_id for history. Status is not history or proof of payment/refund.",
            {"workflow_id":_ID, "run_id":_RUN}, ["workflow_id"]),
    _schema("temporal_list_workflows", "Read one visibility page in configured TEMPORAL_NAMESPACE when workflow_id is unknown. Filter by observed workflow type, ID, status or time using Temporal visibility query. Empty/eventually consistent results do not prove absence. Follow next_page_token with identical query.",
            {"query":{"type":"string", "maxLength":2000, "description":"Visibility filter, e.g. WorkflowType = 'SyntheticFlow'. Empty lists the first page."}, **_PAGE}, []),
    _schema("temporal_history", "Read one history page for exact observed workflow_id AND run_id. Follow next_page_token; preserve eventId/eventType/time and causal event references. History may aggregate retries and does not prove external payment effects. No wait, signal, cancel, terminate, start, reset or workflow query.",
            {"workflow_id":_ID, "run_id":_RUN, **_PAGE}, ["workflow_id", "run_id"]),
]
