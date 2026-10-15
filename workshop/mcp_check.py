#!/usr/bin/env python3
"""MCP handshake/discovery, optional synthetic replay probe; no LLM."""

import argparse
import json
from harness.mcp_client import McpConnection, load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--probe-replay", action="store_true", help="call synthetic resource/event tools; refuses live mode")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.probe_replay and config.get("mode") != "replay":
            raise ValueError("--probe-replay requires explicit mode=replay")
        with McpConnection(config) as connection:
            report = {"mode": config["mode"], "namespace": config["namespace"],
                      "server": connection.client.server_info,
                      "tools": [s["function"]["name"] for s in connection.schemas]}
            if args.probe_replay:
                responses = [connection.call("get-resource", {"namespace": config["namespace"], "resourceType": "pods", "name": "checkout-probe"}),
                             connection.call("list-events", {"namespace": config["namespace"]})]
                report["observations"] = [{"result": r.text, "is_error": r.is_error, **r.metadata} for r in responses]
                if any(r.is_error for r in responses):
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 1
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MCP check failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
