"""File-only adapters. No kubectl, network, dynamic paths, or instructor answer access."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / 'fixtures/trace-to-logs/business-checkout'
TRACE_ID = 'a' * 32
CASES = ('complete', 'missing-logs', 'no-ids', 'incomplete-trace', 'invalid-trace')


def timestamp(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timestamp needs timezone')
    return value.astimezone(timezone.utc)


def windows(trace):
    """Per-service windows; support both OTLP and Tempo resource envelope names."""
    found = {}
    issues = []
    for batch in trace.get('resourceSpans', trace.get('batches', [])):
        service = next((a.get('value', {}).get('stringValue') for a in batch.get('resource', {}).get('attributes', [])
                        if a.get('key') == 'service.name'), None)
        for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', [])):
            for span in scope.get('spans', []):
                try:
                    if not service:
                        raise ValueError('missing service.name')
                    start, end = int(span['startTimeUnixNano']), int(span['endTimeUnixNano'])
                    if end < start:
                        raise ValueError('reversed span')
                    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
                    a = epoch + timedelta(microseconds=start // 1000) - timedelta(seconds=2)
                    b = epoch + timedelta(microseconds=end // 1000) + timedelta(seconds=2)
                    old = found.get(service, (a, b))
                    found[service] = (min(a, old[0]), max(b, old[1]))
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    issues.append(f'incomplete span: {exc}')
    if not found:
        raise ValueError('trace has no usable spans')
    return found, issues


def source(name, case="complete"):
    if case not in CASES:
        raise ValueError('unknown case')
    allowed = {'report': 'report.md', 'pods': 'pods.json', 'trace': 'trace.json', 'code': 'code/checkout.py',
               'checkout_logs':'logs/checkout.jsonl', 'pricing_logs':'logs/pricing.jsonl'}
    if name not in allowed:
        raise ValueError('unknown source; allowed names: ' + ', '.join(allowed))
    path = DATA / allowed[name]
    text = path.read_text(encoding='utf-8')
    if name == 'pricing_logs' and case == 'missing-logs':
        return {'source':allowed[name], 'status':'unavailable', 'data':'synthetic log source unavailable', 'mode':'synthetic_file_replay'}
    if name.endswith('_logs') and case == 'no-ids':
        text='\n'.join(json.dumps({k:v for k,v in json.loads(line).items() if k not in ('trace_id','request_id','order_id')}) for line in text.splitlines())
    if name == 'trace':
        trace=json.loads(text)
        if case == 'invalid-trace':trace={}
        if case == 'incomplete-trace':trace['resourceSpans'][0]['scopeSpans'][0]['spans'].append({'startTimeUnixNano':'broken'})
        text=json.dumps(trace)
    if name == 'code':
        text = '\n'.join(f'{i}: {line}' for i, line in enumerate(text.splitlines(), 1))
    return {'source': f'fixtures/trace-to-logs/business-checkout/{allowed[name]}', 'data': text,
            'mode': 'synthetic_file_replay'}


def investigate(correlate, trace_id=TRACE_ID, extra_keys=None, case='complete', limit=40):
    if case not in CASES or trace_id != TRACE_ID:
        return {'status': 'error', 'error': 'unknown replay case or trace_id', 'services': []}
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        return {'status': 'error', 'error': 'limit must be 1..100', 'services': []}
    if extra_keys is not None and (not isinstance(extra_keys, list) or not all(isinstance(k, str) and k for k in extra_keys)):
        return {'status': 'error', 'error': 'extra_keys must contain nonempty strings', 'services': []}
    trace = json.loads(source('trace',case)['data'])
    try:
        ranges, issues = windows(trace)
    except (ValueError, TypeError) as exc:
        return {'status': 'error', 'error': str(exc), 'services': []}
    result = {'status': 'ok', 'mode': 'synthetic_file_replay', 'trace_id': trace_id,
              'limitations': list(issues), 'services': []}
    for service, (since, until) in sorted(ranges.items()):
        entry = {'service': service, 'source': f'logs/{service}.jsonl', 'since': since.isoformat(),
                 'until': until.isoformat(), 'matches': [], 'context': [], 'truncated': False, 'status': 'ok'}
        if service not in ('checkout', 'pricing') or (case == 'missing-logs' and service == 'pricing'):
            entry.update(status='unavailable', error='synthetic log source unavailable')
            result['limitations'].append(f'{service}: source unavailable')
        else:
            rows, skipped = [], 0
            for line_no, raw in enumerate(source(service+'_logs',case)['data'].splitlines(), 1):
                record = json.loads(raw)
                try:
                    time = timestamp(record['timestamp'])
                except (KeyError, ValueError, TypeError):
                    skipped += 1
                    continue
                rows.append({'time': time, 'ids': {k:record[k] for k in ('trace_id','request_id','order_id') if k in record},
                             'raw':raw, 'line':line_no})
            try:
                selected = correlate(rows, since, until, trace_id, extra_keys or [], limit)
            except NotImplementedError:
                return {'status':'not_implemented', 'error':'Complete correlate in workshop/skills/trace_logs.py', 'services':[]}
            entry.update(selected)
            entry['skipped_invalid_timestamps'] = skipped
            if skipped:
                result['limitations'].append(f'{service}: skipped {skipped} invalid timestamps')
        result['services'].append(entry)
    # Invalid log rows are visible limitations; missing sources/spans make coverage partial.
    if issues or any(s['status']=='unavailable' for s in result['services']) or case == 'incomplete-trace':
        result['status'] = 'partial'
    elif not any(s['matches'] for s in result['services']):
        result['status'] = 'no_matches'
    result['coverage'] = {
        'complete': False,
        'scope': 'one_trace_time_windows_in_file_replay',
        'missing_data_effect': 'unknown',
        'reason': 'Matched rows do not establish that skipped, unavailable or outside-window data are irrelevant.'}
    return result


def tool_text(result):
    """Keep unavailable/unfinished tools distinguishable from application ERROR logs."""
    text=json.dumps(result,ensure_ascii=False)
    if result.get('status') in ('error','unavailable'):
        return 'TOOL ERROR: '+text
    if result.get('status')=='not_implemented':
        return 'NOT IMPLEMENTED: '+text
    return text
