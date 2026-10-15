import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'workshop/offline/verify_stand.py'
spec=importlib.util.spec_from_file_location('offline_check',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Readiness(unittest.TestCase):
 def data(self):return {'items':[{'metadata':{'name':n,'generation':2},'spec':{'replicas':1},'status':{'observedGeneration':2,'updatedReplicas':1,'readyReplicas':1,'availableReplicas':1}} for n in module.EXPECTED]}
 def test_complete(self):self.assertEqual(module.readiness(self.data()),[])
 def test_absent_and_scaled_zero(self):
  d=self.data();name=d['items'][0]['metadata']['name'];d['items'][0]['spec']['replicas']=0
  self.assertIn(name+': not ready',module.readiness(d));d['items'].pop();self.assertTrue(module.readiness(d))
 def test_old_generation_or_not_ready(self):
  for key,value in [('observedGeneration',1),('readyReplicas',0),('updatedReplicas',0),('availableReplicas',0)]:
   d=self.data();d['items'][0]['status'][key]=value;self.assertTrue(module.readiness(d))
