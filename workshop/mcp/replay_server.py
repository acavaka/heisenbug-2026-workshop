#!/usr/bin/env python3
"""Synthetic MCP protocol server; no cluster, network client or LLM access."""

import argparse
import asyncio
import json
from pathlib import Path
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

def schemas():
    fields = {
        "analyze": ({"namespace": "string", "explain": "boolean", "backend": "string", "filters": "array"}, []),
        "get-resource": ({"namespace": "string", "resourceType": "string", "name": "string"}, ["resourceType", "name"]),
        "list-resources": ({"namespace": "string", "resourceType": "string", "labelSelector": "string"}, ["resourceType"]),
        "list-events": ({"namespace": "string", "involvedObjectName": "string", "involvedObjectKind": "string", "limit": "integer"}, []),
        "get-logs": ({"namespace": "string", "podName": "string", "container": "string", "tailLines": "integer", "previous": "boolean", "sinceSeconds": "integer"}, ["namespace", "podName"]),
        "config": ({}, []),
    }
    return [types.Tool(name=name, description=f"SYNTHETIC REPLAY: {name}", inputSchema={
        "type": "object", "properties": {key: {"type": kind} for key, kind in props.items()}, "required": required
    }) for name, (props, required) in fields.items()]


async def serve(case):
    server = Server("qai-synthetic-replay")
    fixture_path = Path(__file__).resolve().parents[2] / 'fixtures/behavioral/infra-startup' / f'{"broken" if case == "slow" else case}.json'
    fixture = json.loads(fixture_path.read_text())

    @server.list_tools()
    async def list_tools():
        return schemas()

    @server.call_tool()
    async def call_tool(name, arguments):
        if case == "slow":
            await asyncio.sleep(30)
        if (arguments.get("namespace") != "qai-training"
                or (name == "get-resource" and (arguments.get("name") != "checkout-probe" or arguments.get("resourceType") not in ("pod", "pods")))
                or (name == "get-logs" and arguments.get("podName") != "checkout-probe")):
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text="synthetic resource not found")])
        if name in fixture['unavailable_tools']:
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text="SYNTHETIC REPLAY: source unavailable")])
        pod = fixture['pod']
        payload = {
            "get-resource": pod,
            "list-resources": {"kind": "PodList", "items": [pod] if pod else []},
            "list-events": fixture['events'],
            "analyze": {"source": "SYNTHETIC REPLAY", "results": [{"name": "qai-training/checkout-probe", "error": e['message']} for e in fixture['events']]},
            "get-logs": fixture['logs'],
        }.get(name)
        if name == "list-resources" and arguments.get("resourceType") not in ("pod", "pods"):
            payload = {"items": []}
        if name == "list-events" and (arguments.get("involvedObjectName", "checkout-probe") != "checkout-probe"
                                       or arguments.get("involvedObjectKind", "Pod") != "Pod"):
            payload = []
        if payload is None:
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text="synthetic unsupported tool")])
        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload)]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["broken", "healthy", "readiness", "unknown", "slow"], default="broken")
    asyncio.run(serve(parser.parse_args().case))
