"""Tool failures and file/CLI boundaries, using synthetic local data only."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workshop"))

from harness.verdict import tool_result_failed
from skills import cluster_logs, context_fixtures, k8sgpt_skill, prom, runbook, tracker
from skills import postgres_query as postgres


class ToolFailureTests(unittest.TestCase):
    def test_grep_preserves_kubectl_failure_instead_of_claiming_no_matches(self):
        proc = subprocess.CompletedProcess([], 1, "partial synthetic logs", "pod unavailable")
        with patch.object(cluster_logs.subprocess, "run", return_value=proc):
            result = cluster_logs.grep_pod_logs("synthetic", "cache hit")
        self.assertTrue(result.startswith("kubectl failed"), result)
        self.assertIn("pod unavailable", result)
        self.assertTrue(tool_result_failed("grep_pod_logs", result))

    def test_missing_kubectl_is_a_diagnostic_for_direct_cli_consumers(self):
        with patch.object(cluster_logs.subprocess, "run", side_effect=FileNotFoundError()):
            result = cluster_logs.kubectl_get_pods()
        self.assertTrue(tool_result_failed("kubectl_get_pods", result))

    def test_no_match_reports_actual_clamped_sample_size(self):
        with patch.object(cluster_logs.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "other", "")):
            result = cluster_logs.grep_pod_logs("synthetic", "target", tail=10000)
        self.assertIn("last 500 lines", result)
        self.assertNotIn("10000", result)

    def test_k8sgpt_nonzero_exit_is_failure_even_with_stdout(self):
        with patch.object(k8sgpt_skill.shutil, "which", return_value="/synthetic/k8sgpt"), patch.object(k8sgpt_skill.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "partial", "backend unavailable")):
            result = k8sgpt_skill.k8sgpt_analyze()
        self.assertTrue(tool_result_failed("k8sgpt_analyze", result), result)
        self.assertIn("backend unavailable", result)

    def test_prometheus_preserves_complete_large_json(self):
        payload = {"status": "success", "data": {"result": [{"metric": {"synthetic": "x" * 10000}}]}}
        with patch.object(prom.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())):
            result = prom.prom_query("synthetic_metric")
        self.assertEqual(payload, json.loads(result))

    def test_prometheus_invalid_json_is_not_a_successful_observation(self):
        with patch.object(prom.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>proxy error</html>")):
            result = prom.prom_query("up")
        self.assertTrue(tool_result_failed("prom_query", result), result)


class FixtureBoundaryTests(unittest.TestCase):
    def test_tracker_cannot_read_parent_or_symlink_outside_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "tracker"
            reports.mkdir()
            (root / "answer.md").write_text("SYNTHETIC HIDDEN ANSWER")
            (reports / "link.md").symlink_to(root / "answer.md")
            (reports / "BUG-SYNTH.md").write_text("synthetic report")
            with patch.object(tracker, "TRACKER_DIR", reports):
                self.assertEqual("synthetic report", tracker.tracker_get("BUG-SYNTH"))
                for name in ("../answer", "link", str(root / "answer")):
                    result = tracker.tracker_get(name)
                    self.assertNotIn("SYNTHETIC HIDDEN ANSWER", result)
                    self.assertTrue(tool_result_failed("tracker_get", result), result)

    def test_context_sources_cannot_read_sibling_or_external_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = root / "fixtures"
            for kind in ("wiki", "testops", "github"):
                (fixtures / kind).mkdir(parents=True)
                (fixtures / kind / "good.md").write_text("synthetic context")
            (root / "answer.md").write_text("SYNTHETIC HIDDEN ANSWER")
            (fixtures / "wiki" / "link.md").symlink_to(root / "answer.md")
            with patch.object(context_fixtures, "FIXTURES", fixtures):
                for name, fn in (("wiki_get", context_fixtures.wiki_get), ("testops_get", context_fixtures.testops_get), ("github_release_notes", context_fixtures.github_release_notes)):
                    self.assertEqual("synthetic context", fn("good.md"))
                    for path in ("../../answer.md", "../wiki/good.md"):
                        result = fn(path)
                        self.assertTrue(tool_result_failed(name, result), result)
                        self.assertNotIn("SYNTHETIC HIDDEN ANSWER", result)
                self.assertTrue(tool_result_failed("wiki_get", context_fixtures.wiki_get("link.md")))

    def test_read_only_blocks_runbook_at_tool_boundary(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"QAI_READ_ONLY": "1"}):
            path = Path(directory) / "runbook.md"
            with patch.object(runbook, "RUNBOOK", path):
                result = runbook.runbook_append("s", "t", "f:1", "BUG-SYNTH")
            self.assertFalse(path.exists())
            self.assertTrue(tool_result_failed("runbook_append", result), result)

    def test_read_only_blocks_arbitrary_sql_at_tool_boundary(self):
        with patch.dict(os.environ, {"QAI_READ_ONLY": "1"}), patch.object(postgres.subprocess, "run") as execute:
            result = postgres.postgres_query("SELECT 1")
        execute.assert_not_called()
        self.assertTrue(tool_result_failed("postgres_query", result), result)


class ToolCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("dotenv.load_dotenv", return_value=False):
            cls.cli = importlib.import_module("qai_tool")

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = self.cli.main(args)
        return status, output.getvalue()

    def test_cli_preserves_numeric_looking_string_identifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "12.md").write_text("synthetic report twelve")
            (root / "null.md").write_text("synthetic report null")
            with patch.object(tracker, "TRACKER_DIR", root):
                # A regex '123' is string data, not an integer for re.compile.
                with patch.object(cluster_logs.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "request 123 failed", "")):
                    code, output = self.invoke(["grep_pod_logs", "deployment=synthetic", "pattern=123"])
                self.assertEqual(0, code, output)
                self.assertIn("request 123 failed", output)
                code, output = self.invoke(["tracker_get", "bug_id=null"])
                self.assertEqual(0, code, output)
                self.assertIn("synthetic report null", output)

    def test_cli_returns_nonzero_on_tool_failure(self):
        with patch.object(cluster_logs.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "unavailable")):
            code, output = self.invoke(["kubectl_get_pods"])
        self.assertEqual(1, code, output)
        self.assertIn("kubectl failed", output)

    def test_cli_argument_error_does_not_escape_as_traceback(self):
        code, output = self.invoke(["kubectl_logs", "unknown=synthetic"])
        self.assertNotEqual(0, code)
        self.assertIn("TOOL ERROR:", output)

    def test_cli_missing_required_argument_is_a_controlled_tool_error(self):
        code, output = self.invoke(["kubectl_logs"])
        self.assertEqual(1, code)
        self.assertIn("TOOL ERROR:", output)
        self.assertNotIn("Traceback", output)

    def test_cli_read_only_flag_blocks_write_tool(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=False):
            path = Path(directory) / "runbook.md"
            with patch.object(runbook, "RUNBOOK", path):
                code, output = self.invoke(["--read-only", "runbook_append", "symptom=s", "first_skill=t", "culprit=f:1", "bug_id=BUG-SYNTH"])
            self.assertEqual(1, code, output)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
