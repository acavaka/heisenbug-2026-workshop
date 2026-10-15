#!/usr/bin/env python3
"""Print a local host config fragment; never edit host settings."""

import argparse
import json
from pathlib import Path
import sys

WORKSHOP = Path(__file__).resolve().parent


def render(host, profile="replay"):
    config = WORKSHOP / "mcp" / ("replay.json" if profile == "replay" else "live.example.json")
    args = [str(WORKSHOP / "mcp_gateway.py"), "--config", str(config)]
    if host == "python":
        return json.dumps({"QAI_MCP_CONFIG": str(config)}, indent=2)
    if host == "codex":
        # JSON basic strings/arrays are valid TOML for these values.
        result = "[mcp_servers.k8sgpt]\ncommand = " + json.dumps(sys.executable) + "\nargs = " + json.dumps(args) + "\n"
        if profile == "live":
            result += 'env_vars = ["QAI_KUBECONFIG"]\n'
        return result
    return json.dumps({"mcpServers": {"k8sgpt": {"command": sys.executable, "args": args}}}, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["python", "codex", "cursor", "claude"], required=True)
    parser.add_argument("--profile", choices=["replay", "live"], default="replay")
    options = parser.parse_args()
    print(render(options.host, options.profile))
