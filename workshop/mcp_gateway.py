#!/usr/bin/env python3
"""Read-only MCP-to-MCP gateway for native clients. No kubectl or CLI analyze."""

import argparse
import asyncio
import sys
from functools import partial

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.client.stdio as client_stdio

from harness.mcp_client import load_config, open_session
from harness.evidence_mcp import EvidenceGateway

_terminate_upstream = client_stdio._terminate_process_tree


async def serve(config):
    # SDK 1.30.0 defaults to 2s on both nested hops. k8sgpt ignores stdin EOF;
    # give the inner shutdown a shorter grace period so the outer client does
    # not terminate the gateway before it reaps k8sgpt. Local to this process.
    client_stdio.PROCESS_TERMINATION_TIMEOUT = 0.25
    # k8sgpt can also ignore SIGTERM; reserve time for SDK SIGKILL escalation.
    client_stdio._terminate_process_tree = partial(_terminate_upstream, timeout_seconds=0.25)
    async with open_session(config) as upstream:
        server = Server("qai-k8sgpt-gateway")
        evidence = EvidenceGateway(upstream)

        @server.list_tools()
        async def list_tools():
            return upstream.tools + evidence.tools

        @server.call_tool()
        async def call_tool(name, arguments):
            try:
                if name in evidence.schemas:
                    return await evidence.call(name, arguments)
                result, _ = await upstream.call(name, arguments)
                return result
            except Exception as exc:
                return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=f"MCP ERROR: {type(exc).__name__}: {exc}")])

        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="explicit upstream config, live or replay")
    args = parser.parse_args()
    try:
        asyncio.run(serve(load_config(args.config)))
        return 0
    except Exception as exc:
        print(f"MCP gateway startup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
