"""Shared replay transition: collect correlation before permitting RCA investigation.

No LLM and no answer key here. Runtime abstention is explicitly labelled; it is
not a model answer and does not establish a root cause. Existing eval is separate.
"""
import json
from exercises.trace_to_logs.adapters import TRACE_ID, investigate, source, timestamp


def correlation_decision(result):
    refs=[]
    if result.get('status') in ('ok','partial'):
        for service in result.get('services',[]):
            for row in service.get('matches',[]):
                try:
                    record=json.loads(row['raw'])
                    if (record.get('trace_id') == result.get('trace_id') == TRACE_ID
                            and 'trace_id' in row.get('matched_by',[])
                            and timestamp(service['since']) <= timestamp(record['timestamp']) <= timestamp(service['until'])):
                        refs.append({'source':service['source'],'line':row['line'],'trace_id':record['trace_id']})
                except (KeyError,TypeError,ValueError,AttributeError):
                    continue
    return {'rca_allowed':bool(refs),'state':'correlated' if refs else 'needs_evidence',
            'evidence':refs,'scope':'trace_to_logs file replay; exact trace_id and time window',
            'next_step':'investigate_cause' if refs else 'collect_logs_with_request_ids',
            'reason':'Correlation permits investigation, not confirmation of root cause.' if refs else
                     'No verified trace-to-log link. Context and suspected code cannot confirm this request cause.'}


def prepare(correlate,case='complete'):
    observations=[]
    for name in ('report','pods'):
        observations.append({'tool':'replay_source','args':{'name':name},'result':source(name,case)})
    result=investigate(correlate,TRACE_ID,case=case)
    observations.append({'tool':'trace_to_logs','args':{'trace_id':TRACE_ID},'result':result})
    decision=correlation_decision(result)
    report=None
    if not decision['rca_allowed']:
        report={'diagnosis':'unknown','calculation':None,'code_quote':'',
                'excluded_message':'','excluded_request_id':'','data_complete':False,
                'skipped_data_effect':'unknown','next_step':'collect_evidence'}
    return {'case':case,'correlation':decision,'observations':observations,'report':report,
            'report_origin':'runtime' if report else None,'raw_answer':None}


def collect_cause_inputs(bundle):
    """Second stage: read code/raw alternatives only after a successful link check."""
    if not bundle['correlation']['rca_allowed']:
        return bundle
    for name in ('code','checkout_logs'):
        bundle['observations'].append({'tool':'replay_source','args':{'name':name},
                                       'result':source(name,bundle['case'])})
    return bundle
