import importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'workshop/offline/launch.py';s=importlib.util.spec_from_file_location('launch',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fresh(unittest.TestCase):
 def test_existing_cluster_is_protected(self):
  with self.assertRaises(ValueError):m.require_fresh('qai-boutique',['qai-boutique'],Path('/nonexistent/qai-config'))
 def test_existing_kubeconfig_is_protected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config';p.write_text('private');
   with self.assertRaises(ValueError):m.require_fresh('new',[],p)
   self.assertEqual(p.read_text(),'private')
 def test_fresh_allowed(self):m.require_fresh('new',['qai-boutique'],Path('/nonexistent/qai-config'))
