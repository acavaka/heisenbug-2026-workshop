"""Public entry points work without instructor solutions or behavioral answer keys."""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workshop'))


class PublicRunnerTests(unittest.TestCase):
    def test_cli_help_has_no_instructor_switch(self):
        for script in ('application_mcp.py', 'exercises/trace_to_logs/run.py',
                       'exercises/trace_to_logs/orchestrator_replay.py', 'replay.py'):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, str(ROOT/'workshop'/script), '--help'],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('--solution', result.stdout)

    def test_file_report_needs_no_model(self):
        result = subprocess.run([sys.executable, str(ROOT/'workshop/exercises/trace_to_logs/run.py'),
                                 'report'], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('BUG-LAB-01', json.dumps(json.loads(result.stdout)))

    def test_application_contract_acceptance_is_not_behavioral_pass(self):
        from exercises.trace_to_logs.orchestrator_replay import check_public_verdict
        with patch('harness.verdict.validate_verdict', return_value=[]) as validator:
            result = check_public_verdict({'orchestration': {'status': 'accepted'}})
        validator.assert_called_once_with({'orchestration': {'status': 'accepted'}},
                                          expected_bug_id='BUG-LAB-01')
        self.assertTrue(result['contract_valid'])
        self.assertEqual(result['behavioral_eval']['status'], 'not_run')
        self.assertNotIn('passed', result)

    def test_application_rejects_invalid_and_unsubmitted_reports(self):
        from exercises.trace_to_logs.orchestrator_replay import check_public_verdict
        self.assertFalse(check_public_verdict({})['contract_valid'])
        with patch('harness.verdict.validate_verdict', return_value=[]):
            self.assertFalse(check_public_verdict({})['contract_valid'])

    def test_infra_failure_propagates_without_private_eval(self):
        import replay
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'run'
            with patch.object(replay.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(replay.main(['--cases', 'healthy', '--output', str(output)]), 1)
            result = json.loads((output/'summary.json').read_text())[0]
            self.assertFalse(result['contract_valid'])
            self.assertEqual(result['behavioral_eval']['status'], 'not_run')

    def test_infra_checks_full_contract_and_marks_ungraded(self):
        import replay
        def fake_process(*args, **kwargs):
            Path(kwargs['env']['REPORTS_DIR'], 'BUG-INFRA-01.json').write_text('{}')
            return subprocess.CompletedProcess([], 0)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'run'
            with patch.object(replay.subprocess, 'run', side_effect=fake_process), \
                    patch.object(replay, 'validate_verdict', return_value=[]) as validator, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(replay.main(['--cases', 'healthy', '--output', str(output)]), 0)
            validator.assert_called_once_with({}, expected_bug_id='BUG-INFRA-01')
            result = json.loads((output/'summary.json').read_text())[0]
            self.assertTrue(result['contract_valid'])
            self.assertEqual(result['behavioral_eval']['status'], 'not_run')

    def test_infra_does_not_overwrite_previous_run(self):
        import replay
        with tempfile.TemporaryDirectory() as tmp, patch.object(replay.subprocess, 'run') as run, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(replay.main(['--output', tmp]), 2)
            run.assert_not_called()

    def test_application_gateway_observes_without_solution_and_guards_code(self):
        from application_mcp import ApplicationGateway, ReplayTools
        async def exercise():
            gateway = ApplicationGateway(lambda bug: ReplayTools(bug, 'complete'))
            response = await gateway.call('qai_begin', {'bug_id': 'BUG-LAB-01'})
            catalog = json.loads(response.content[0].text)
            sid = catalog['investigation_id']
            response = await gateway.call('qai_observe', {'investigation_id': sid,
                'tool': 'tracker_get', 'arguments': {'bug_id': 'BUG-LAB-01'}})
            self.assertFalse(response.isError)
            self.assertIn('observation_id', json.loads(response.content[0].text))
            with self.assertRaisesRegex(ValueError, 'blocked by correlation gate'):
                await gateway.call('qai_observe', {'investigation_id': sid,
                    'tool': 'read_file', 'arguments': {'path': 'checkout.py'}})
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
