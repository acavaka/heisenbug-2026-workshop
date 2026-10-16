import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
m=json.loads((root/'USB-MANIFEST.json').read_text())
for i in m['files']:
 p=root/i['path']
 if not p.is_file() or p.stat().st_size!=i['size'] or hashlib.file_digest(p.open('rb'),'sha256').hexdigest()!=i['sha256']:raise SystemExit('Checksum failed: '+i['path'])
print('PASS:',len(m['files']),'files verified')
