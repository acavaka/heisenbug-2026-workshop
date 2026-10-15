#!/usr/bin/env python3
"""Participant file tools and correlation contract checks.

For an investigation use orchestrator_replay.py or application MCP.
Private solutions and behavioral answer keys are not part of this CLI."""
import argparse
import json
from pathlib import Path
import sys
WORKSHOP=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(WORKSHOP))
from exercises.trace_to_logs.adapters import CASES, TRACE_ID, investigate, source, tool_text


def acceptance(correlate):
    failures=[]
    complete=investigate(correlate, extra_keys=['req-lab-1'])
    if complete['status']!='ok': failures.append('complete status')
    hits=[x for s in complete['services'] for x in s['matches']]
    if not any('AMOUNT_MISMATCH' in x['raw'] for x in hits): failures.append('missing target error')
    if any('INVENTORY_DOWN' in x['raw'] or 'PREFIX_TRAP' in x['raw'] or 'late same id' in x['raw'] for x in hits): failures.append('unrelated or out-of-window match')
    if not all(x.get('matched_by') for x in hits): failures.append('missing correlation basis')
    noids=investigate(correlate,case='no-ids')
    if noids['status']!='no_matches' or not any(s['context'] for s in noids['services']): failures.append('no-id context')
    missing=investigate(correlate,case='missing-logs')
    if missing['status']!='partial' or not any(s['matches'] for s in missing['services']): failures.append('partial data')
    if investigate(correlate,case='invalid-trace')['status']!='error': failures.append('invalid trace')
    if investigate(correlate,case='incomplete-trace')['status']!='partial': failures.append('incomplete trace')
    capped=investigate(correlate,limit=1)
    if not any(s['truncated'] for s in capped['services']) or any(len(s['matches'])>1 or len(s['context'])>1 for s in capped['services']): failures.append('output cap')
    # Independent values prevent a trace-only implementation passing by accident.
    from datetime import datetime, timezone, timedelta
    start=datetime(2026,1,1,tzinfo=timezone.utc);end=start+timedelta(seconds=2)
    specs=[('start',start,{'trace_id':'target'}),('end',end,{'trace_id':'target'}),
           ('request',start,{'request_id':'request-7'}),('order',end,{'order_id':'order-8'}),
           ('foreign',start,{'request_id':'request-70'}),('context',start,{}),
           ('outside',end+timedelta(microseconds=1),{'trace_id':'target'})]
    rows=[{'raw':name,'time':time,'ids':ids,'line':i+1} for i,(name,time,ids) in enumerate(specs)]
    try:
        selected=correlate(rows,start,end,'target',['request-7','order-8'],40)
    except NotImplementedError:
        failures.append('correlation TODO')
    else:
        expected={'start':['trace_id'],'end':['trace_id'],'request':['request_id'],'order':['order_id']}
        actual={r['raw']:r['matched_by'] for r in selected['matches']}
        if actual!=expected or len(selected['matches'])!=4: failures.append('exact IDs, business keys and boundaries')
        if [r['raw'] for r in selected['context']]!=['context']: failures.append('foreign or matched records in context')
    return {'passed':not failures,'failures':failures}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['report','pods','trace','code','checkout_logs','pricing_logs','trace_to_logs','check','prepare'])
    p.add_argument('--case',choices=CASES,default='complete')
    p.add_argument('--report',type=Path,help='Save the local result')
    args=p.parse_args()
    from skills.trace_logs import correlate
    if args.action in ('report','pods','trace','code','checkout_logs','pricing_logs'):
        result=source(args.action,args.case)
    elif args.action=='check':
        result=acceptance(correlate)
    elif args.action=='prepare':
        from exercises.trace_to_logs.workflow import prepare
        result=prepare(correlate,args.case)
    else:
        result=investigate(correlate,TRACE_ID,case=args.case)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.action=='check': return 0 if result['passed'] else 1
    if args.action=='prepare': return 0 if result['correlation']['rca_allowed'] else 1
    return 1 if result.get('status') in ('error','not_implemented') else 0


if __name__=='__main__':
    raise SystemExit(main())
