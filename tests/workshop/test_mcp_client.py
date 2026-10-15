"""Real stdio MCP against a synthetic server; never uses kubeconfig or an LLM."""

import json
from pathlib import Path
import sys
import time
import unittest

WORKSHOP = Path(__file__).resolve().parents[2] / "workshop"
sys.path.insert(0, str(WORKSHOP))


def replay_config(case="broken"):
    return {"command": sys.executable, "args": [str(WORKSHOP / "mcp/replay_server.py"), "--case", case],
            "namespace": "qai-training", "timeout_s": 3, "mode": "replay"}


class McpClientTests(unittest.TestCase):
    def test_discovers_calls_and_keeps_mcp_provenance(self):
        from harness.mcp_client import McpConnection

        with McpConnection(replay_config()) as connection:
            names = {t["function"]["name"] for t in connection.schemas}
            self.assertIn("mcp_k8sgpt_get_resource", names)
            self.assertNotIn("mcp_k8sgpt_config", names)
            result = connection.call("get-resource", {"resourceType": "pods", "name": "checkout-probe", "namespace": "qai-training"})
            self.assertFalse(result.is_error, result.text)
            self.assertEqual("synthetic-pod-uid", json.loads(result.text)["metadata"]["uid"])
            self.assertEqual("get-resource", result.metadata["mcp"]["tool"])
            self.assertEqual("replay", result.metadata["mcp"]["mode"])
        self.assertTrue(connection.closed)

    def test_policy_blocks_mutation_secrets_other_namespaces_and_explain(self):
        from harness.mcp_client import McpConnection

        with McpConnection(replay_config()) as connection:
            cases = [
                ("config", {}),
                ("get-resource", {"resourceType": "secrets", "name": "x", "namespace": "qai-training"}),
                ("list-events", {"namespace": "default"}),
                ("list-events", {}),
                ("analyze", {"namespace": "qai-training", "explain": True}),
                ("analyze", {"namespace": "qai-training", "backend": "other"}),
            ]
            for name, args in cases:
                with self.subTest(name=name, args=args):
                    self.assertTrue(connection.call(name, args).is_error)

    def test_protocol_error_stays_error_and_session_can_continue(self):
        from harness.mcp_client import McpConnection

        with McpConnection(replay_config()) as connection:
            bad = connection.call("get-resource", {"resourceType": "pods", "name": "absent", "namespace": "qai-training"})
            self.assertTrue(bad.is_error)
            self.assertIn("not found", bad.text)
            self.assertFalse(connection.call("list-events", {"namespace": "qai-training"}).is_error)

    def test_timeout_is_bounded_and_cleanup_completes(self):
        from harness.mcp_client import McpConnection

        config = replay_config("slow")
        config["timeout_s"] = 1
        started = time.monotonic()
        with McpConnection(config) as connection:
            result = connection.call("list-events", {"namespace": "qai-training"})
            self.assertTrue(result.is_error)
        self.assertTrue(connection.closed)
        self.assertLess(time.monotonic() - started, 10)

    def test_gateway_is_real_mcp_and_applies_same_policy(self):
        from harness.mcp_client import McpConnection

        config = replay_config()
        config["args"] = [str(WORKSHOP / "mcp_gateway.py"), "--config", str(WORKSHOP / "mcp/replay.json")]
        config["timeout_s"] = 10
        with McpConnection(config) as connection:
            self.assertFalse(connection.call("analyze", {"namespace": "qai-training", "explain": False}).is_error)
            self.assertTrue(connection.call("add-filters", {"filters": ["Pod"]}).is_error)

    @unittest.skipIf(sys.platform == "win32", "POSIX process lifecycle")
    def test_gateway_reaps_upstream_that_ignores_eof(self):
        import os
        import tempfile
        from harness.mcp_client import McpConnection
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pid"
            wrapper = Path(tmp) / "stubborn.py"
            wrapper.write_text("import os, pathlib, runpy, time, signal\n"
                               + "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                               + f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                               + f"runpy.run_path({str(WORKSHOP / 'mcp/replay_server.py')!r}, run_name='__main__')\n"
                               + "time.sleep(60)\n")
            upstream = replay_config()
            upstream["args"] = [str(wrapper)]
            config_path = Path(tmp) / "upstream.json"
            config_path.write_text(json.dumps(upstream))
            config = replay_config()
            config["args"] = [str(WORKSHOP / "mcp_gateway.py"), "--config", str(config_path)]
            config["timeout_s"] = 10
            pid = None
            try:
                with McpConnection(config):
                    pid = int(pidfile.read_text())
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return
                self.fail("Gateway left its upstream process alive after disconnect")
            finally:
                if pid:
                    try: os.kill(pid, 9)
                    except ProcessLookupError: pass

    def test_missing_server_has_no_cli_fallback(self):
        from harness.mcp_client import McpConnection

        config = replay_config()
        config["command"] = "/no-such-synthetic-mcp-binary"
        with self.assertRaises(Exception):
            with McpConnection(config):
                self.fail("Connection must fail")


if __name__ == "__main__":
    unittest.main()
