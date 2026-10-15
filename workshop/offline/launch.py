#!/usr/bin/env python3
"""Fresh offline stand startup. Refuses existing clusters; uses a private kubeconfig.
No pull/build and no model calls. Requires the USB archive and installed Docker/Kind.
"""
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def require_fresh(name,clusters,kubeconfig):
 if name in clusters:raise ValueError('Cluster already exists: '+name+'. Refusing to change it. Use read-only readiness/port-forward for a prepared stand.')
 if kubeconfig.exists():raise ValueError('Kubeconfig already exists: '+str(kubeconfig)+'. Choose a new private file; do not overwrite credentials.')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--usb',type=Path,required=True);p.add_argument('--cluster-name',default='qai-boutique');p.add_argument('--kubeconfig',type=Path,default=ROOT/'workshop/.local/kind.kubeconfig');p.add_argument('--allow-amd64-emulation',action='store_true');a=p.parse_args()
 try:
  clusters=subprocess.check_output(['kind','get','clusters'],text=True).splitlines();cfg=a.kubeconfig.resolve();require_fresh(a.cluster_name,clusters,cfg)
  manifest=json.loads((a.usb/'images/images-manifest.json').read_text());refs=manifest['images']
  if not manifest.get('complete'):raise ValueError('Incomplete USB image archive')
  # Preserve different local builds under these names; never replace them silently.
  missing=False
  for image in refs:
   r=subprocess.run(['docker','image','inspect',image['ref']],capture_output=True,text=True)
   if r.returncode:missing=True
   elif json.loads(r.stdout)[0]['Id']!=image['id']:raise ValueError('Local image tag has different content: '+image['ref'])
  compressed=a.usb/'images/workshop-images.tar.gz'
  if hashlib.file_digest(compressed.open('rb'),'sha256').hexdigest()!=manifest['compressed_sha256']:raise ValueError('USB image archive checksum mismatch')
  dest=ROOT/'microservices-demo/hack/offline/images';dest.mkdir(parents=True,exist_ok=True)
  archive=dest/'usb.tar'
  if not archive.exists():
   with gzip.open(compressed,'rb') as src,archive.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
  if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=manifest['archive_sha256']:raise ValueError('Local image tar checksum mismatch')
  # The legacy loader will load this tar again; loading here provides preflight coverage.
  if missing:subprocess.run(['docker','load','-i',str(archive)],check=True)
  preflight=[sys.executable,str(Path(__file__).with_name('preflight_images.py'))]
  if a.allow_amd64_emulation:preflight.append('--allow-amd64-emulation')
  subprocess.run(preflight,check=True)
  cfg.parent.mkdir(parents=True,exist_ok=True)
  env=dict(os.environ,KUBECONFIG=str(cfg),CLUSTER_NAME=a.cluster_name)
  # Python venv interpreter also satisfies the shell generator's python3 command.
  env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','')
  for script in (ROOT/'microservices-demo/hack/offline').glob('*.sh'):script.chmod(script.stat().st_mode|0o100)
  subprocess.run(['bash','hack/offline/up-offline.sh'],cwd=ROOT/'microservices-demo',env=env,check=True)
  subprocess.run([sys.executable,str(Path(__file__).with_name('verify_stand.py')),'--context','kind-'+a.cluster_name,'--kubeconfig',str(cfg)],env=env,check=True)
  print('READY: expected deployments verified. Private kubeconfig: '+str(cfg))
  return 0
 except (ValueError,OSError,subprocess.CalledProcessError) as e:
  print('Offline startup failed: '+str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
