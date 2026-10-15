#!/usr/bin/env python3
"""Read-only HTTP checks using temporary free localhost ports and an explicit context."""
import argparse,json,select,socket,subprocess,sys,time,urllib.request
SERVICES=[('frontend',80,'/_healthz'),('grafana',3000,'/api/health'),('tempo',3200,'/ready'),('prometheus',9090,'/-/ready'),('temporal-ui',8080,'/'),('order-worker',8088,'/healthz')]
def main():
 p=argparse.ArgumentParser();p.add_argument('--context',required=True);p.add_argument('--kubeconfig',required=True);a=p.parse_args();results=[]
 for svc,remote,path in SERVICES:
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  proc=subprocess.Popen(['kubectl','--kubeconfig',a.kubeconfig,'--context',a.context,'-n','default','port-forward','--address=127.0.0.1','svc/'+svc,f'{port}:{remote}'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  try:
   deadline=time.monotonic()+20;ready=False
   while time.monotonic()<deadline:
    if proc.poll() is not None:break
    if select.select([proc.stdout],[],[],0.25)[0]:
     if 'Forwarding from 127.0.0.1:' in proc.stdout.readline():ready=True;break
   if not ready:raise RuntimeError('Port-forward did not start')
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   with opener.open(f'http://127.0.0.1:{port}'+path,timeout=10) as response:results.append({'service':svc,'status':response.status,'ok':response.status==200})
  except Exception as e:results.append({'service':svc,'ok':False,'error':str(e)})
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 print(json.dumps({'valid':all(r['ok'] for r in results),'context':a.context,'checks':results},indent=2));return not all(r['ok'] for r in results)
if __name__=='__main__':sys.exit(main())
