"""Reference input for application verdicts; the full validator stays unchanged.

Catalog entries are exact successful tool output lines, never role summaries.
No diagnosis, confidence or claim is inferred here.
"""
from copy import deepcopy
import re


def catalog(observations, scope):
    entries = []
    files = []
    for index, observation in enumerate(observations, 1):
        if observation.get('status') != 'ok':
            continue
        tool, result = observation['tool'], observation['result']
        header = re.search(r'^File: (.+)$', result, re.M) if tool == 'read_file' else None
        for number, line in enumerate(result.splitlines(), 1):
            if not line.strip():
                continue
            entry = {'id':f'{scope}:A{index}L{number}', 'source':tool, 'quote':line}
            location = None
            if header:
                match = re.match(r'^\s*([1-9]\d*):', line)
                if match:
                    location = f'{header[1]}:{match[1]}'
            elif tool == 'code_search':
                match = re.match(r'^(.+):([1-9]\d*):', line)
                if match:
                    location = f'{match[1]}:{match[2]}'
            if location:
                entry['file_line'] = location
                if location not in files:
                    files.append(location)
            entries.append(entry)
    return {'evidence':entries, 'observed_file_lines':files}


def expand(draft, available):
    """Expand the reference form, or preserve the legacy full form for API callers."""
    result = deepcopy(draft)
    errors = []
    by_id = {e['id']:e for e in available['evidence']}
    evidence = result.get('evidence', [])
    if not isinstance(evidence, list):
        return result, errors  # Full validator reports the malformed evidence field.
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or 'evidence_ref' not in item:
            continue  # Legacy draft still goes through the unchanged validator.
        ref = item.pop('evidence_ref')
        if 'source' in item or 'quote' in item:
            errors.append(f'evidence[{index}]: do not mix references and source/quote')
            continue
        if ref == '' and item.get('kind') in ('ВЫВОД','ГИПОТЕЗА'):
            item.update(source='', quote='')
        elif not isinstance(ref, str) or ref not in by_id:
            errors.append(f'evidence[{index}]: unknown application evidence_ref')
        else:
            item.update(source=by_id[ref]['source'], quote=by_id[ref]['quote'])
    return result, errors
