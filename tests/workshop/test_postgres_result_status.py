"""Subprocess failures are diagnostics, never successful stand observations."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workshop"))

from harness.verdict import tool_result_failed
from skills import postgres_query as postgres


class PostgresResultStatusTests(unittest.TestCase):
    def test_transport_failure_is_explicit_even_with_partial_stdout(self):
        completed = subprocess.CompletedProcess([], 1, stdout="partial synthetic output\n", stderr="error: unable to upgrade connection: synthetic postgres pod not found\n")
        with patch.object(postgres.subprocess, "run", return_value=completed):
            result = postgres.postgres_query("SELECT 1")
        self.assertTrue(result.startswith("postgres_query failed:"))
        self.assertIn("code 1", result)
        self.assertTrue(tool_result_failed("postgres_query", result))

    def test_successful_rows_are_preserved(self):
        output = "order_id | status\nSYNTHETIC-1 | PENDING\n(1 row)\n"
        with patch.object(postgres.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=output, stderr="")):
            result = postgres.postgres_query("SELECT order_id, status FROM orders")
        self.assertEqual(output, result)
        self.assertFalse(tool_result_failed("postgres_query", result))


if __name__ == "__main__":
    unittest.main()
