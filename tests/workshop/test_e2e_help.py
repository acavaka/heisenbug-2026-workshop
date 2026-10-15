import os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class HelpTests(unittest.TestCase):
 def test_help_without_key_and_without_reports(self):
  env=dict(os.environ,OPENAI_API_KEY='',AGENT_TRACES='0')
  result=subprocess.run([sys.executable,str(ROOT/'workshop/e2e.py'),'--help'],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('--mode workflow',result.stdout)
