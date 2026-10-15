#!/usr/bin/env python3
"""Strict read-only readiness: no success when any expected deployment is absent/unready."""
import argparse,json,subprocess,sys,time
EXPECTED={'adservice','cartservice','checkoutservice','currencyservice','emailservice','frontend','paymentservice','productcatalogservice','recommendationservice','redis-cart','shippingservice','postgres','tempo','prometheus','grafana','temporal','temporal-ui','order-worker'}
def readiness(data):
 found={i['metadata']['name']:i for i in data['items']};errors=[]
 for name in sorted(EXPECTED):
  if name not in found:errors.append(name+': missing');continue
  i=found[name];spec=i['spec'];status=i.get('status',{});desired=spec.get('replicas',1)
  if desired<1 or status.get('observedGeneration',0)<i['metadata'].get('generation',1) or status.get('updatedReplicas',0)!=desired or status.get('readyReplicas',0)!=desired or status.get('availableReplicas',0)!=desired:errors.append(name+': not ready')
 return errors

def main():
 p=argparse.ArgumentParser();p.add_argument('--context',required=True);p.add_argument('--kubeconfig',required=True);p.add_argument('--timeout',type=float,default=600);a=p.parse_args()
 deadline=time.monotonic()+a.timeout;errors=[]
 while True:
  r=subprocess.run(['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'--request-timeout=10s','get','deployments','-n','default','-o','json'],capture_output=True,text=True)
  errors=readiness(json.loads(r.stdout)) if r.returncode==0 else ['Cannot read deployments: '+r.stderr.strip()]
  if not errors or time.monotonic()>=deadline:break
  time.sleep(min(5,max(0,deadline-time.monotonic())))
 print(json.dumps({'valid':not errors,'context':a.context,'expected_deployments':len(EXPECTED),'errors':errors},indent=2))
 return bool(errors)
if __name__=='__main__':sys.exit(main())
