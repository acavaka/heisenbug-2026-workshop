#!/usr/bin/env python3
"""Refresh USB file manifests and a pre-Python shasum checklist; no network."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--usb',type=Path,required=True);p.add_argument('--verified-kind-environment',default=None);a=p.parse_args();root=a.usb.resolve()
files=[]
for f in sorted(root.rglob('*')):
 if not f.is_file() or f.name in {'USB-MANIFEST.json','USB-SHA256SUMS.txt'}:continue
 if f.is_symlink() or '__pycache__' in f.parts or f.suffix=='.part':raise SystemExit('Unexpected unfinished/private file: '+str(f))
 files.append({'path':str(f.relative_to(root)),'size':f.stat().st_size,'sha256':hashlib.file_digest(f.open('rb'),'sha256').hexdigest()})
manifest={'platform':'macOS arm64 Python 3.12','images_complete':json.loads((root/'images/images-manifest.json').read_text())['complete'],'installers_included':True,'clean_kind_boot_verified':bool(a.verified_kind_environment),'kind_boot_environment':a.verified_kind_environment,'clean_docker_installer_boot_verified':False,'files':files}
m=root/'USB-MANIFEST.json';m.write_text(json.dumps(manifest,indent=2))
checks=files+[{'path':m.name,'sha256':hashlib.sha256(m.read_bytes()).hexdigest()}]
(root/'USB-SHA256SUMS.txt').write_text(''.join(i['sha256']+'  '+i['path']+'\n' for i in checks))
print(f'{len(files)} files; {sum(i["size"] for i in files)} bytes; SHA checklist ready before Python installation')
