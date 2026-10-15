#!/usr/bin/env python3
"""Lead only: repackage locally installed distributions, without network access.
Produces platform-specific wheels; not claimed to be original publisher artifacts.
"""
import argparse,base64,csv,hashlib,importlib.metadata as md,io,json,re,sys,zipfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 out=args.output;out.mkdir(parents=True,exist_ok=True);records=[];lock=[]
 for dist in md.distributions():
  name=dist.metadata['Name'];version=dist.version
  if name.lower() in {'pip','setuptools','wheel'}:continue
  files=list(dist.files or []);wheel=next((f for f in files if str(f).endswith('.dist-info/WHEEL')),None)
  if wheel is None:raise RuntimeError(f'No wheel metadata: {name}')
  meta=dist.locate_file(wheel).read_text();tags=re.findall(r'^Tag: (.+)$',meta,re.M)
  if not tags:raise RuntimeError(f'No compatibility tag: {name}')
  tag=tags[0];stem=str(wheel).split('/')[0].removesuffix('.dist-info')
  dest=out/f'{stem}-{tag}.whl';row=[]
  with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
   for f in files:
    rel=str(f);src=Path(dist.locate_file(f))
    if not src.is_file() or '..' in Path(rel).parts or '__pycache__' in Path(rel).parts or rel.endswith(('.pyc','/RECORD','/INSTALLER','/REQUESTED','/direct_url.json')):continue
    data=src.read_bytes();z.writestr(rel,data)
    digest=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode();row.append([rel,'sha256='+digest,str(len(data))])
   record=str(wheel).rsplit('/',1)[0]+'/RECORD';row.append([record,'','']);buf=io.StringIO();csv.writer(buf).writerows(row);z.writestr(record,buf.getvalue())
  records.append({'file':dest.name,'name':name,'version':version,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'origin':'repacked from local installed distribution; RECORD regenerated; generated scripts excluded'})
  lock.append(f'{name}=={version} --hash=sha256:{records[-1]["sha256"]}')
 (out/'requirements.lock').write_text('\n'.join(sorted(lock,key=str.lower))+'\n')
 (out/'manifest.json').write_text(json.dumps({'python':sys.version,'platform':sys.platform,'artifacts':records},indent=2))
 print(f'Prepared {len(records)} local wheels; no downloads')
if __name__=='__main__':main()
