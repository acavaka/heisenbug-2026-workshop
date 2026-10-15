#!/usr/bin/env python3
"""Read-only check: refuse offline stand startup with missing/wrong-platform images."""
import argparse,json,platform,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
refs=[x.split('|')[1] for raw in (root/'microservices-demo/hack/offline/image-list.txt').read_text().splitlines() if (x:=raw.split('#')[0].strip())]
refs+=['boutique/productcatalogservice:workshop-bug1024','boutique/frontend:workshop-bug1024']
parser=argparse.ArgumentParser();parser.add_argument('--allow-amd64-emulation',action='store_true',help='Explicitly accept amd64 service images on arm64; requires verified Docker emulation');args=parser.parse_args()
warnings=[]
arch={'arm64':'arm64','aarch64':'arm64','x86_64':'amd64','AMD64':'amd64'}.get(platform.machine())
errors=[]
for ref in refs:
 r=subprocess.run(['docker','image','inspect',ref],capture_output=True,text=True)
 if r.returncode:errors.append('Missing local image: '+ref);continue
 d=json.loads(r.stdout)[0]
 if d['Os']!='linux' or d['Architecture']!=arch:
  if args.allow_amd64_emulation and arch=='arm64' and d['Architecture']=='amd64' and d['Os']=='linux' and not ref.startswith('kindest/'):
   warnings.append('Requires emulation: '+ref)
  else:errors.append('Wrong platform: '+ref+' '+d['Os']+'/'+d['Architecture'])
print(json.dumps({'valid':not errors,'architecture':arch,'errors':errors,'warnings':warnings,'images_checked':len(refs)},indent=2))
sys.exit(bool(errors))
