"""Real stdio MCP transport against synthetic upstream, without API keys."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RUN = "00000000-0000-4000-8000-000000000001"


class TemporalMcpTests(unittest.TestCase):
    def test_list_describe_history_and_verdict_boundary_over_stdio(self):
        async def scenario():
            env = {k:v for k,v in os.environ.items() if k not in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL")}
            env.update(TEMPORAL_NAMESPACE="synthetic-only", TEMPORAL_HOST="unused.invalid:7233")
            params = StdioServerParameters(command=sys.executable,
                args=[str(Path(__file__).with_name("temporal_mcp_stub.py"))], env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as client:
                    await client.initialize()
                    async def call(name, args, error=False):
                        response = await client.call_tool(name, args)
                        self.assertEqual(error, bool(response.isError), response.content[0].text)
                        return json.loads(response.content[0].text)
                    begin = await call("qai_begin", {"bug_id":"BUG-SYNTH"})
                    sid = begin["investigation_id"]
                    async def observe(tool, args, error=False):
                        return await call("qai_observe", {"investigation_id":sid,"tool":tool,"arguments":args}, error)
                    listing = await observe("temporal_list_workflows", {"page_size":1})
                    page = json.loads(listing["result"])
                    self.assertTrue(page["has_more"])
                    self.assertEqual(RUN, page["workflows"][0]["run_id"])
                    second = await observe("temporal_list_workflows", {"page_size":1,"page_token":page["next_page_token"]})
                    self.assertEqual([], json.loads(second["result"])["workflows"])
                    described = await observe("temporal_inspect", {"workflow_id":"synthetic-order", "run_id":RUN})
                    self.assertEqual(RUN, json.loads(described["result"])["run_id"])
                    history = await observe("temporal_history", {"workflow_id":"synthetic-order", "run_id":RUN})
                    self.assertEqual("1", json.loads(history["result"])["events"][0]["eventId"])
                    evidence = history["catalog"]["evidence"]
                    failed = await observe("temporal_list_workflows", {"query":"synthetic failure"}, error=True)
                    self.assertEqual(evidence, failed["catalog"]["evidence"])
                    self.assertIn("TOOL ERROR", failed["result"])
                    entry = next(e for e in evidence if e["source"] == "temporal_history" and '"eventId"' in e["quote"])
                    draft = dict(bug_id="BUG-SYNTH", investigation_type="application",root_cause="",culprit_files=[],confidence="low",
                        reasons=["Cause unknown"],evidence=[dict(kind="ФАКТ",claim="Observed event ID 1",evidence_ref=entry["id"])],
                        false_leads=[],red_team=["a","b","c"],limitations=["Synthetic transport test, no live incident"],fix_direction="Collect correlated evidence")
                    accepted = await call("qai_validate", {"investigation_id":sid,"draft":draft})
                    self.assertTrue(accepted["valid"])
                    draft.update(confidence="high",root_cause="Unsupported cause")
                    rejected = await call("qai_validate", {"investigation_id":sid,"draft":draft}, error=True)
                    self.assertFalse(rejected["valid"])
                    self.assertIn("high confidence requires grounded code and stand facts", rejected["errors"])
        asyncio.run(asyncio.wait_for(scenario(), timeout=20))


if __name__ == "__main__":
    unittest.main()
