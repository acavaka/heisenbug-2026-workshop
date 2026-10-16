#!/usr/bin/env python3
"""Install the matching offline wheel pack; refuse wrong OS/CPU or existing venv."""
import argparse,hashlib,json,platform,subprocess,sys,venv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--wheels',type=Path,required=True);p.add_argument('--venv',type=Path,default=Path('workshop/.venv'));a=p.parse_args()
manifest=json.loads((a.wheels/'manifest.json').read_text())
actual=(sys.platform,platform.machine())
expected={'darwin':('darwin','arm64'),'linux':('linux','x86_64')}.get(manifest.get('platform'))
if actual!=expected or sys.version_info[:2]!=(3,12):
 raise SystemExit(f'Wheel pack platform mismatch: needs {expected} Python 3.12, got {actual} {sys.version_info[:2]}. No network fallback.')
for item in manifest['artifacts']:
 if hashlib.file_digest((a.wheels/item['file']).open('rb'),'sha256').hexdigest()!=item['sha256']:raise SystemExit('Wheel checksum failed: '+item['file'])
if a.venv.exists():raise SystemExit('Refusing to overwrite existing venv; use a new --venv directory.')
venv.EnvBuilder(with_pip=True).create(a.venv)
py=a.venv.resolve()/'bin/python'
subprocess.run([str(py),'-m','pip','--isolated','install','--no-index','--no-cache-dir','--only-binary=:all:','--require-hashes','--find-links',str(a.wheels.resolve()),'-r',str((a.wheels/'requirements.lock').resolve())],check=True)
subprocess.run([str(py),'-m','pip','check'],check=True)
print('Offline dependencies installed; no API key or network download.')
