#!/usr/bin/env python3
"""Lead: save existing Docker images only; no pull/build/cluster mutation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-incomplete',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
refs=[x.split('|')[1] for raw in (root/'microservices-demo/hack/offline/image-list.txt').read_text().splitlines() if (x:=raw.split('#')[0].strip())]
refs+=['boutique/productcatalogservice:workshop-bug1024','boutique/frontend:workshop-bug1024'];images=[];missing=[]
for ref in refs:
 r=subprocess.run(['docker','image','inspect',ref],capture_output=True,text=True)
 if r.returncode:missing.append(ref);continue
 d=json.loads(r.stdout)[0];images.append({'ref':ref,'id':d['Id'],'os':d['Os'],'architecture':d['Architecture']})
report={'images':images,'missing':missing,'complete':not missing,'network_downloads':False}
(a.output/'images-manifest.json').write_text(json.dumps(report,indent=2))
if missing and not a.allow_incomplete:raise SystemExit('Missing local images: '+', '.join(missing)+'. No download fallback.')
archive=a.output/'workshop-images.tar'
if archive.exists():raise SystemExit('Refusing overwrite')
subprocess.run(['docker','save','-o',str(archive),*[i['ref'] for i in images]],check=True)
report['archive_sha256']=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest();report['archive_bytes']=archive.stat().st_size
(a.output/'images-manifest.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'archive':str(archive),'complete':not missing,'missing':missing,'bytes':archive.stat().st_size}))
