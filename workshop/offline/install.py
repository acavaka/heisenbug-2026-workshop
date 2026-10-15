#!/usr/bin/env python3
"""Participant offline dependency install: macOS arm64 Python 3.12 only."""
import argparse,hashlib,json,platform,subprocess,sys,venv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--wheels',type=Path,required=True);p.add_argument('--venv',type=Path,default=Path('workshop/.venv'));a=p.parse_args()
if sys.platform!='darwin' or platform.machine()!='arm64' or sys.version_info[:2]!=(3,12):
 raise SystemExit('This wheel pack requires macOS arm64, Python 3.12. Obtain the matching platform pack; no network fallback.')
manifest=json.loads((a.wheels/'manifest.json').read_text())
for item in manifest['artifacts']:
 if hashlib.sha256((a.wheels/item['file']).read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Wheel checksum failed: '+item['file'])
if a.venv.exists():raise SystemExit('Refusing to overwrite existing venv; use a new --venv directory.')
venv.EnvBuilder(with_pip=True).create(a.venv)
py=a.venv.resolve()/'bin/python'
subprocess.run([str(py),'-m','pip','--isolated','install','--no-index','--no-cache-dir','--only-binary=:all:','--require-hashes','--find-links',str(a.wheels.resolve()),'-r',str((a.wheels/'requirements.lock').resolve())],check=True)
subprocess.run([str(py),'-m','pip','check'],check=True)
print('Offline dependencies installed; no API key or network download.')
