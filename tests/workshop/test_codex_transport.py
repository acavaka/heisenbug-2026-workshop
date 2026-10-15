import importlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'workshop'))

class CodexTransportTests(unittest.TestCase):
    def test_decision_schema_limits_tools_without_requiring_api_key(self):
        transport = importlib.import_module('harness.codex_transport')
        schema = transport.decision_schema([{'type':'function','function':{'name':'qai_state'}}])
        self.assertEqual(['qai_state'],schema['properties']['tool_calls']['items']['properties']['name']['enum'])
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual({'content','tool_calls'},set(schema['required']))

    def test_native_execution_is_rejected(self):
        transport = importlib.import_module('harness.codex_transport')
        with self.assertRaises(ValueError):
            transport.check_events(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))
        transport.check_events(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'done'}}))

    def test_clean_environment_excludes_api_credentials(self):
        transport = importlib.import_module('harness.codex_transport')
        env = transport.clean_env({'PATH':'/bin','OPENAI_API_KEY':'secret','CODEX_API_KEY':'secret','OPENAI_BASE_URL':'other','CODEX_HOME':'/auth'})
        self.assertNotIn('OPENAI_API_KEY',env)
        self.assertNotIn('CODEX_API_KEY',env)
        self.assertNotIn('OPENAI_BASE_URL',env)
        self.assertEqual('/auth',env['CODEX_HOME'])

    def test_codex_mode_neither_loads_dotenv_nor_constructs_api_client(self):
        import os
        import subprocess
        program = '''
from unittest.mock import patch
with patch('dotenv.load_dotenv', side_effect=AssertionError('dotenv must not load')), patch('openai.OpenAI', side_effect=AssertionError('API client must not be constructed')):
    from harness import agent
    assert agent.client is None
    assert agent.CODEX_TRANSPORT
'''
        env = {**os.environ,'QAI_LLM_TRANSPORT':'codex','PYTHONPATH':str(Path(__file__).resolve().parents[2]/'workshop')}
        result = subprocess.run([sys.executable,'-c',program],env=env,text=True,capture_output=True)
        self.assertEqual(0,result.returncode,result.stderr)
