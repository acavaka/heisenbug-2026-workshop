#!/usr/bin/env python3
"""BUG-LAB-01 file tools for the real model-directed QAI orchestrator.

Only the selected LLM transport uses the network. No live tools or MCP fallback.
Run each case in a fresh process: the existing code validator uses BOUTIQUE_ROOT,
which here points exclusively to the synthetic code snapshot, never Boutique.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

WORKSHOP = Path(__file__).resolve().parents[2]
if str(WORKSHOP) not in sys.path:
    sys.path.insert(0, str(WORKSHOP))
from exercises.trace_to_logs.adapters import CASES, DATA, TRACE_ID, investigate, source, tool_text
from exercises.trace_to_logs.workflow import correlation_decision


class ReplayBackend:
    def __init__(self, case, correlate):
        if case not in CASES:
            raise ValueError('Unknown case')
        self.case, self.correlate = case, correlate
        self.correlation = None
        self.reports = []

    @staticmethod
    def _json(raw, fallback):
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else fallback
        except ValueError:
            return fallback

    def _infra_session(self):
        raise ValueError('This file backend has no infrastructure evidence catalog')

    def execution_context(self):
        from agents.orchestrator import observations
        seen = {o['tool'] for o in observations() if o.get('status') == 'ok'}
        gaps = [name for name in ('tracker_get','kubectl_get_pods','trace_to_logs') if name not in seen]
        # A failed trace is an observed limitation, not a reason for endless retries.
        if self.correlation is not None and 'trace_to_logs' in gaps:
            gaps.remove('trace_to_logs')
        return {'mode':'synthetic_file_replay', 'case':self.case,
                'collection_gaps':gaps,
                'roles':{'analyzer':['tracker_get'],
                         'investigator':['kubectl_get_pods','tempo_get_trace','trace_to_logs','kubectl_logs'],
                         'checker':['read_file: checkout.py, only after correlation']},
                'correlation':self.correlation,
                'instructions':('Прочитай репорт, снимок pods и вызови trace_to_logs для проверки корреляции. '
                    'Это независимые проверки, порядок и досбор выбирает оркестратор. '
                    'Код доступен checker после rca_allowed=true; при отсутствии связи '
                    'останови подтверждение RCA и запроси недостающие данные. '
                    'Используй обычный application-вердикт QAI, а не компактный JSON упражнения.')}

    def delegation_guard(self, role):
        if role == 'checker' and (not self.correlation or not self.correlation['rca_allowed']):
            return {'error':'correlation_required', 'correlation':self.correlation,
                    'next_step':'investigator: trace_to_logs; if needs_evidence, abstain and request correlated data',
                    'code_status':'not_read_due_to_correlation_gate, not an unavailable source'}
        return None

    def read(self, name):
        result = source(name, self.case)
        if result.get('status') == 'unavailable':
            return tool_text(result)
        return f"mode=synthetic_file_replay case={self.case} source={result['source']}\n{result['data']}"

    def tracker_get(self, bug_id):
        if bug_id != 'BUG-LAB-01':
            raise ValueError('Only BUG-LAB-01 is available')
        return self.read('report')

    def trace_to_logs(self, trace_id, extra_keys=None, limit=40):
        result = investigate(self.correlate, trace_id, extra_keys, self.case, limit)
        self.correlation = correlation_decision(result)
        return tool_text({**result, 'correlation': self.correlation})

    def tempo_get_trace(self, trace_id):
        if trace_id != TRACE_ID:
            raise ValueError('Unknown replay trace_id')
        return tool_text(source('trace', self.case))

    def kubectl_logs(self, service):
        if service not in ('checkout', 'pricing'):
            raise ValueError('Only checkout and pricing file logs are available')
        return self.read(service + '_logs')

    def read_file(self, path):
        from skills import code
        if path != 'checkout.py' or code.BOUTIQUE_ROOT.resolve() != (DATA/'code').resolve():
            raise ValueError('Only fixture checkout.py is allowed in the isolated replay source root')
        return 'mode=synthetic_file_replay\n' + code.read_file(path)

    def tools(self, role):
        def spec(name, description, props, required):
            return {'type':'function','function':{'name':name,
                'description':'Synthetic file replay only. ' + description,
                'parameters':{'type':'object','properties':props,'required':required,'additionalProperties':False}}}
        string = {'type': 'string'}
        if role == 'qai-report-analyzer':
            schemas = [spec('tracker_get', 'Read BUG-LAB-01 report.', {'bug_id':string}, ['bug_id'])]
            impl = {'tracker_get':self.tracker_get}
        elif role == 'qai-data-investigator':
            schemas = [
                spec('kubectl_get_pods', 'Read pod snapshot.', {}, []),
                spec('tempo_get_trace', 'Read full trace snapshot.', {'trace_id':string}, ['trace_id']),
                spec('trace_to_logs', 'Correlate trace and logs; returns matches/context, coverage and runtime correlation gate. This performs the prepare correlation check; it does not confirm root cause.',
                     {'trace_id':string, 'extra_keys':{'type':'array','items':string}, 'limit':{'type':'integer'}}, ['trace_id']),
                spec('kubectl_logs', 'Read original service logs including excluded records.', {'service':{'type':'string','enum':['checkout','pricing']}}, ['service']),
            ]
            impl = {'kubectl_get_pods':lambda:self.read('pods'), 'tempo_get_trace':self.tempo_get_trace,
                    'trace_to_logs':self.trace_to_logs, 'kubectl_logs':self.kubectl_logs}
        elif role == 'qai-hypothesis-checker':
            from skills import code
            if not self.correlation or not self.correlation['rca_allowed']:
                raise ValueError('Correlation is not established; collect evidence instead of confirming RCA')
            if code.BOUTIQUE_ROOT.resolve() != (DATA/'code').resolve():
                raise ValueError('Replay requires an isolated fixture code root')
            schemas = [spec('read_file', 'Read the only available source snapshot checkout.py with line numbers.',
                            {'path':{'type':'string','enum':['checkout.py']}}, ['path'])]
            impl = {'read_file':self.read_file}
        else:
            raise ValueError('Unsupported replay role')
        return schemas, impl

    def _run(self, role, task, *, infrastructure_review=False):
        from harness.agent import run_role
        if infrastructure_review:
            raise ValueError('No infrastructure catalog in this replay')
        schemas, impl = self.tools(role)
        task += (f'\nExecution scope: synthetic_file_replay, case={self.case}, read-only. '
                 'Только предоставленные файловые инструменты; стенд/MCP/БД недоступны в этом режиме. '
                 'trace_to_logs выполняет ту же проверку correlation, что команда prepare; '
                 'отдельная shell-команда prepare здесь не нужна. '
                 'Единственный доступный исходник — checkout.py (снимок учебного сервиса); '
                 'пути Boutique/order-worker из общей инструкции относятся к live-режиму. '
                 'Подтверждение корреляции разрешает проверку причины, но не доказывает её. '
                 'Итог — обычный application-контракт QAI; учебный компактный JSON здесь не используется.')
        result = run_role(role, task, schemas, impl)
        self.reports.append({'role':role, 'report':result})
        return result


def check_public_verdict(report):
    """Run the unchanged full validator; no private answer key or inferred grade."""
    from harness.verdict import validate_verdict
    errors = validate_verdict(report, expected_bug_id='BUG-LAB-01')
    if report.get('orchestration', {}).get('status') != 'accepted':
        errors.append('orchestrator did not accept a submission')
    return {'contract_valid': not errors, 'contract_errors': errors,
            'behavioral_eval': {'status': 'not_run', 'reason': 'Private answer key; human review still required'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, default='complete')
    parser.add_argument('--provider', choices=['openai','codex'], default='openai')
    parser.add_argument('--model', help='OpenAI model or Codex model; omitted uses gpt-4.1 or the CLI default respectively')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; use a fresh directory')
    if args.provider == 'openai':
        from dotenv import load_dotenv
        load_dotenv(WORKSHOP/'.env')
        os.environ.pop('QAI_LLM_TRANSPORT', None)
    else:
        os.environ['QAI_LLM_TRANSPORT'] = 'codex'
        for name in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL'):
            os.environ.pop(name, None)
    args.model = args.model or ('codex-default' if args.provider == 'codex' else 'gpt-4.1')
    os.environ.update(MODEL=args.model, MODEL_FAST=args.model, MODEL_STRONG=args.model,
                      QAI_READ_ONLY='1', AGENT_TRACES='0', BOUTIQUE_ROOT=str(DATA/'code'),
                      ORDER_WORKER_ROOT=str(DATA/'unavailable-order-worker'))
    os.environ.pop('QAI_MCP_CONFIG', None)
    from skills.trace_logs import correlate
    from agents.orchestrator import Investigation
    from harness import trace
    backend = ReplayBackend(args.case, correlate)
    output.mkdir(parents=True)
    files = [*WORKSHOP.joinpath('prompts').glob('*.md'),
             WORKSHOP/'agents/orchestrator.py', WORKSHOP/'harness/agent.py',
             WORKSHOP/'harness/verdict.py', WORKSHOP/'harness/infra_verdict.py',
             WORKSHOP/'harness/application_evidence.py', WORKSHOP/'harness/codex_transport.py',
             WORKSHOP/'skills/trace_logs.py',
             WORKSHOP/'harness/evidence.py', *Path(__file__).parent.glob('*.py')]
    (output/'source-hashes.json').write_text(json.dumps({str(p.relative_to(WORKSHOP.parent)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2)+'\n')
    start = time.monotonic()
    trace.start_run('BUG-LAB-01', output)
    try:
        report = Investigation('BUG-LAB-01', backend).run()
    finally:
        telemetry = trace.end_run(export=False)
    report['replay'] = {'case':args.case, 'mode':'synthetic_file_replay', 'model':args.model, 'provider':args.provider,
                        'code_root':str(DATA/'code'),
                        'correlation':backend.correlation, 'elapsed_s':round(time.monotonic()-start, 2)}
    report['trace'] = telemetry
    checks = check_public_verdict(report)
    (output/'BUG-LAB-01.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (output/'role-reports.json').write_text(json.dumps(backend.reports, ensure_ascii=False, indent=2)+'\n')
    (output/'validation.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'case':args.case,'elapsed_s':report['replay']['elapsed_s'], **checks}, ensure_ascii=False))
    return 0 if checks['contract_valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
