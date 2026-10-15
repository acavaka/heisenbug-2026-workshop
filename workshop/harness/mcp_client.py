"""MCP stdio client with discovery, persistent session, policy and sync bridge."""

from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import partial
import json
import os
from pathlib import Path
import re
import sys

import anyio
from anyio.from_thread import start_blocking_portal
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from harness.mcp_policy import ALLOWED_TOOLS, restrict_schema, validate_arguments
from harness.tool_result import ToolResult

WORKSHOP = Path(__file__).resolve().parents[1]


def load_config(path: str | Path) -> dict:
    """Explicit local config. No .env reads, no implicit global host settings."""
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    tokens = {"PYTHON": sys.executable, "WORKSHOP": str(WORKSHOP), "REPO": str(WORKSHOP.parent)}

    def expand(value):
        if isinstance(value, str):
            def replace(match):
                key = match[1]
                replacement = tokens.get(key, os.environ.get(key))
                if not replacement:
                    raise ValueError(f"MCP config requires environment variable {key}")
                return replacement
            return re.sub(r"\$\{([A-Z_][A-Z_0-9]*)\}", replace, value)
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        return value

    return expand(data)


def validate_config(config: dict) -> None:
    if not isinstance(config, dict) or not isinstance(config.get("command"), str) or not config["command"]:
        raise ValueError("MCP config requires command")
    if not isinstance(config.get("args", []), list) or not all(isinstance(x, str) for x in config.get("args", [])):
        raise ValueError("MCP args must be a string array")
    if not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?", config.get("namespace", "")):
        raise ValueError("MCP config requires a single explicit Kubernetes namespace")
    timeout = config.get("timeout_s", 15)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise ValueError("MCP timeout_s must be in (0, 120]")
    if config.get("mode") not in {"live", "replay"}:
        raise ValueError("MCP config mode must be live or replay")


def tool_alias(name: str) -> str:
    return "mcp_k8sgpt_" + name.replace("-", "_")


def response_result(response, metadata):
    """Identical raw text/error normalization for Python and native MCP capture."""
    content = [part.text for part in response.content if isinstance(part, types.TextContent)]
    if response.structuredContent is not None and not content:
        content = [json.dumps(response.structuredContent, ensure_ascii=False)]
    unsupported = any(not isinstance(part, types.TextContent) for part in response.content)
    if unsupported:
        content.append("MCP result contains unsupported non-text content")
    if sum(len(t) for t in content) > 200_000:
        return ToolResult("MCP ERROR: result exceeds 200000 characters; narrow the query", True, metadata)
    metadata["mcp"]["is_error"] = response.isError
    return ToolResult("\n".join(content), bool(response.isError or unsupported), metadata)


class AsyncTools:
    def __init__(self, session, config, tools, server_info):
        self.session, self.config = session, config
        self.tools, self.server_info = tools, server_info
        self.schemas = {tool.name: tool.inputSchema for tool in tools}

    async def call(self, name, arguments):
        effective = validate_arguments(name, arguments, self.schemas)
        with anyio.fail_after(self.config.get("timeout_s", 15)):
            result = await self.session.call_tool(name, effective)
        return result, effective


@asynccontextmanager
async def open_session(config: dict):
    validate_config(config)
    params = StdioServerParameters(command=config["command"], args=config.get("args", []),
                                   env=config.get("env"), cwd=config.get("cwd", str(WORKSHOP.parent)))
    timeout = config.get("timeout_s", 15)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=timeout)) as session:
            with anyio.fail_after(timeout):
                initialized = await session.initialize()
                tools, seen, cursor = [], set(), None
                for _ in range(10):
                    page = await session.list_tools(cursor=cursor)
                    for tool in page.tools:
                        if tool.name in seen:
                            raise ValueError(f"Duplicate MCP tool: {tool.name}")
                        seen.add(tool.name)
                        if tool.name in ALLOWED_TOOLS:
                            schema = restrict_schema(tool.name, tool.inputSchema, config["namespace"])
                            tools.append(tool.model_copy(update={"inputSchema": schema}))
                    cursor = page.nextCursor
                    if cursor is None:
                        break
                else:
                    raise ValueError("MCP discovery exceeded 10 pages")
                missing = {"get-resource", "list-events"} - {t.name for t in tools}
                if missing:
                    raise ValueError(f"Required MCP tools missing: {sorted(missing)}")
            yield AsyncTools(session, config, tools, initialized.serverInfo.model_dump())


class McpConnection:
    """One subprocess/session for a whole synchronous role, closed even on errors."""
    def __init__(self, config: dict):
        self.config = config
        self.closed = True

    def __enter__(self):
        self._stack = ExitStack()
        try:
            self.portal = self._stack.enter_context(start_blocking_portal())
            self.client = self._stack.enter_context(self.portal.wrap_async_context_manager(open_session(self.config)))
            self.schemas = [{"type": "function", "function": {
                "name": tool_alias(t.name), "description": f"MCP k8sgpt ({self.config['mode']}): {t.description or t.name}",
                "parameters": t.inputSchema,
            }} for t in self.client.tools]
            self.impl = {tool_alias(t.name): partial(self._invoke, t.name) for t in self.client.tools}
            self.closed = False
            return self
        except BaseException:
            self._stack.close()
            raise

    def __exit__(self, *exc):
        try:
            return self._stack.__exit__(*exc)
        finally:
            self.closed = True

    def _invoke(self, tool_name, /, **arguments):
        return self.call(tool_name, arguments)

    def call(self, name: str, arguments: dict) -> ToolResult:
        metadata = {"mcp": {"server": "k8sgpt", "tool": name, "transport": "stdio",
                            "mode": self.config["mode"], "server_info": self.client.server_info},
                    "observed_at": datetime.now(timezone.utc).isoformat()}
        try:
            if self.closed:
                raise RuntimeError("MCP session is closed")
            response, effective = self.portal.call(self.client.call, name, arguments)
            metadata["effective_args"] = effective
            return response_result(response, metadata)
        except Exception as exc:
            # Avoid echoing config/env; error details belong to the operation only.
            detail = "request timed out" if isinstance(exc, TimeoutError) else str(exc)
            return ToolResult(f"MCP ERROR: {type(exc).__name__}: {detail}", True, metadata)
