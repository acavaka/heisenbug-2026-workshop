"""Synthetic read-only Temporal contracts; no model, cluster or bug answer keys."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workshop"))
from skills import temporal_inspect as temporal
from application_mcp import ApplicationGateway, LiveTools
from harness.verdict import tool_result_failed, validate_verdict
from temporalio.api.history.v1 import HistoryEvent

RUN = "00000000-0000-4000-8000-000000000001"


class Page:
    def __init__(self, rows, token=b""):
        self.current_page = rows
        self.next_page_token = token
        self.fetch_next_page = AsyncMock()


def execution():
    return SimpleNamespace(id="synthetic-order", run_id=RUN,
                           status=SimpleNamespace(name="RUNNING"), workflow_type="SyntheticFlow",
                           start_time=None, execution_time=None, close_time=None)


class TemporalToolsTests(unittest.TestCase):
    def setUp(self):
        self.client = unittest.mock.Mock()
        self.connect = patch("temporalio.client.Client.connect", new_callable=AsyncMock)
        self.mock_connect = self.connect.start()
        self.addCleanup(self.connect.stop)
        self.mock_connect.return_value = self.client

    def test_list_reads_one_page_and_preserves_continuation_scope(self):
        self.client.list_workflows.return_value = Page([execution()], b"next")
        first = json.loads(temporal.temporal_list_workflows(query="WorkflowType = 'SyntheticFlow'", page_size=2))
        self.assertEqual(RUN, first["workflows"][0]["run_id"])
        self.assertEqual("RUNNING", first["workflows"][0]["status"])
        self.assertTrue(first["has_more"])
        self.assertFalse(first["continued"])
        cursor = first["next_page_token"]
        self.client.list_workflows.return_value = Page([])
        second = json.loads(temporal.temporal_list_workflows(query="WorkflowType = 'SyntheticFlow'", page_size=2, page_token=cursor))
        self.assertTrue(second["continued"])
        self.assertEqual(b"next", self.client.list_workflows.call_args.kwargs["next_page_token"])
        self.assertFalse(second["has_more"])
        self.mock_connect.assert_awaited_with(temporal.TEMPORAL_HOST, namespace=temporal.TEMPORAL_NAMESPACE)
        bad = temporal.temporal_list_workflows(query="WorkflowType = 'Other'", page_token=cursor)
        self.assertTrue(tool_result_failed("temporal_list_workflows", bad))
        self.assertEqual(2, self.mock_connect.await_count)

    def test_history_pins_run_and_does_not_wait_for_new_events(self):
        event = HistoryEvent(event_id=12, event_type=10)
        handle = self.client.get_workflow_handle.return_value
        handle.fetch_history_events.return_value = Page([event], b"next")
        result = json.loads(temporal.temporal_history("synthetic-order", RUN, page_size=3))
        self.client.get_workflow_handle.assert_called_once_with("synthetic-order", run_id=RUN)
        self.assertFalse(handle.fetch_history_events.call_args.kwargs["wait_new_event"])
        self.assertEqual("12", result["events"][0]["eventId"])
        self.assertTrue(result["has_more"])
        self.assertIn("retry", result["limitations"][0])
        bad = temporal.temporal_history("another-order", RUN, page_token=result["next_page_token"])
        self.assertTrue(tool_result_failed("temporal_history", bad))
        self.assertEqual(1, self.mock_connect.await_count)

    def test_invalid_arguments_fail_before_connect(self):
        for kwargs in ({"page_size":0}, {"page_size":101}, {"page_size":True}, {"page_token":"!"}, {"query":"x"*2001}):
            self.assertTrue(tool_result_failed("temporal_list_workflows", temporal.temporal_list_workflows(**kwargs)))
        for workflow, run in (("", RUN), ("synthetic", ""), ("synthetic", "not-a-run")):
            self.assertTrue(tool_result_failed("temporal_history", temporal.temporal_history(workflow, run)))
        self.mock_connect.assert_not_awaited()

    def test_empty_history_is_not_error_or_proof_of_no_side_effect(self):
        self.client.get_workflow_handle.return_value.fetch_history_events.return_value = Page([])
        result = json.loads(temporal.temporal_history("synthetic-order", RUN))
        self.assertEqual([], result["events"])
        self.assertFalse(result["has_more"])
        self.assertTrue(result["limitations"])

    def test_oversized_response_is_controlled_error_not_broken_json(self):
        row = execution(); row.workflow_type = "x" * 150000
        self.client.list_workflows.return_value = Page([row])
        result = temporal.temporal_list_workflows()
        self.assertTrue(tool_result_failed("temporal_list_workflows", result))
        self.assertIn("response", result)

    def test_connect_timeout_and_server_error_are_not_observations(self):
        async def slow(*args, **kwargs):
            await asyncio.sleep(1)
        self.mock_connect.side_effect = slow
        with patch.object(temporal, "TOTAL_TIMEOUT_S", 0.01):
            result = temporal.temporal_list_workflows()
        self.assertTrue(tool_result_failed("temporal_list_workflows", result))
        self.mock_connect.side_effect = RuntimeError("synthetic service unavailable")
        result = temporal.temporal_history("synthetic-order", RUN)
        self.assertTrue(tool_result_failed("temporal_history", result))

    def test_describe_accepts_run_id_and_keeps_old_call_compatible(self):
        self.client.get_workflow_handle.return_value.describe = AsyncMock(return_value=execution())
        self.assertEqual(RUN, json.loads(temporal.temporal_inspect("synthetic-order", run_id=RUN))["run_id"])
        self.client.get_workflow_handle.assert_called_with("synthetic-order", run_id=RUN)
        self.assertEqual("synthetic-order", json.loads(temporal.temporal_inspect("synthetic-order"))["workflow_id"])

    def test_gateway_executes_actual_temporal_tool_outside_event_loop(self):
        self.client.get_workflow_handle.return_value.describe = AsyncMock(return_value=execution())
        async def run():
            gateway = ApplicationGateway(LiveTools)
            begin = json.loads((await gateway.call("qai_begin", {"bug_id":"BUG-SYNTH"})).content[0].text)
            response = await gateway.call("qai_observe", {"investigation_id":begin["investigation_id"],
                "tool":"temporal_inspect", "arguments":{"workflow_id":"synthetic-order"}})
            self.assertFalse(response.isError, response.content[0].text)
            value = json.loads(response.content[0].text)
            self.assertIn(RUN, value["result"])
            self.assertTrue(value["catalog"]["evidence"])
        asyncio.run(run())

    def test_new_tools_are_available_to_investigator_and_live_gateway(self):
        from harness.prompts import load_prompt
        from skills import tools_for
        names = {"temporal_list_workflows", "temporal_history"}
        self.assertTrue(names <= set(load_prompt("qai-data-investigator").tools))
        schemas, impl = tools_for(list(names))
        self.assertEqual(names, set(impl))
        live = LiveTools("BUG-SYNTH").available()[1]
        self.assertTrue(names <= set(live))
        self.assertFalse({"postgres_query", "runbook_append"} & set(live))

    def test_new_stand_sources_do_not_bypass_high_code_requirement(self):
        for tool in ("temporal_list_workflows", "temporal_history"):
            report = dict(bug_id="BUG-SYNTH", root_cause="hypothesis", confidence="high",
                culprit_files=[], reasons=["observed"], false_leads=[], red_team=["a","b","c"],
                limitations=[], fix_direction="investigate", evidence=[dict(claim="Observed status",kind="ФАКТ",source=tool,quote="RUNNING")],
                tool_observations=[dict(tool=tool,args={},result="RUNNING",status="ok")])
            self.assertIn("high confidence requires grounded code and stand facts", validate_verdict(report))
            report["confidence"] = "medium"
            self.assertEqual([], validate_verdict(report))
            report["tool_observations"][0]["status"] = "error"
            self.assertTrue(validate_verdict(report))


if __name__ == "__main__":
    unittest.main()
