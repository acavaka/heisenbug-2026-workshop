#!/usr/bin/env python3
"""Run real LLM investigations against isolated synthetic MCP.

The public runner checks the existing verdict contract, not the private answer key.

Never accepts a live MCP config. New output directory required to exclude stale reports.
API credentials are loaded only by e2e.py from the existing workshop/.env.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from harness.verdict import validate_verdict
CASES = ('healthy', 'broken', 'unknown', 'readiness')

WORKSHOP = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', choices=CASES, nargs='+', default=list(CASES))
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--model', help='Optional process-only model override for both role groups')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 10:
        parser.error('--repeats must be between 1 and 10')
    output = args.output.resolve()
    if output.exists():
        print('Output already exists; choose a new directory. No reports were overwritten.', file=sys.stderr)
        return 2
    output.mkdir(parents=True)
    results = []
    for case in args.cases:
        for repeat in range(1, args.repeats + 1):
            directory = output / f'{case}-{repeat}'
            directory.mkdir()
            config = directory / 'mcp.json'
            config.write_text(json.dumps(dict(command=sys.executable,
                args=[str(WORKSHOP/'mcp/replay_server.py'),'--case',case],
                namespace='qai-training',mode='replay',exclusive=True,timeout_s=15)))
            env = {**os.environ, 'QAI_MCP_CONFIG':str(config), 'REPORTS_DIR':str(directory),
                   'QAI_READ_ONLY':'1', 'AGENT_TRACES':'0'}
            if args.model:
                env.update(MODEL=args.model, MODEL_FAST=args.model, MODEL_STRONG=args.model)
            print(f'Running {case} #{repeat} (synthetic MCP, real LLM)...', flush=True)
            try:
                with (directory/'console.log').open('w') as log:
                    process = subprocess.run([sys.executable,'-u',str(WORKSHOP/'e2e.py'),'--read-only','BUG-INFRA-01'],
                                             cwd=WORKSHOP.parent, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
                if process.returncode:
                    raise RuntimeError(f'investigation exited {process.returncode}')
                report = json.loads((directory/'BUG-INFRA-01.json').read_text())
                errors = validate_verdict(report, expected_bug_id='BUG-INFRA-01')
                result = dict(contract_valid=not errors, contract_errors=errors,
                              behavioral_eval={'status':'not_run','reason':'Private answer key; review observations manually'})
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                result = dict(contract_valid=False,contract_errors=['investigation_failed'],error=str(exc), behavioral_eval={'status':'not_run'})
            result.update(case=case,repeat=repeat,report=str(directory/'BUG-INFRA-01.json'))
            results.append(result)
            (output/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
            print(('CONTRACT ACCEPTED' if result['contract_valid'] else 'FAILED') + f' {case} #{repeat}: {result["contract_errors"]}', flush=True)
    return 0 if all(r['contract_valid'] for r in results) else 1


if __name__=='__main__':raise SystemExit(main())
