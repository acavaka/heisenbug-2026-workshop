"""Runtime-owned infrastructure observations and references.
Application uses a separate ApplicationSession/catalog; profile IDs are not interchangeable.

This compiler formats selected evidence. It never selects a diagnosis or confidence.
Only execution code calls record(); MCP exposes no observation-import operation.
"""
from copy import deepcopy
import json
import secrets

from harness.infra_verdict import KEYS, RESOURCE_KINDS, quoted, reference
from harness.infra_collection import collection_gaps
from harness.verdict import tool_result_failed, validate_verdict


def _json_spans(text):
    """Decode JSON while retaining literal value spans (no reserialization quotes)."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('nonfinite JSON value')

    decoder = json.JSONDecoder(object_pairs_hook=unique, parse_constant=invalid_constant)
    spans = {}

    def space(pos):
        while pos < len(text) and text[pos] in ' \t\n\r':
            pos += 1
        return pos

    def walk(pos, path):
        pos = space(pos)
        value, end = decoder.raw_decode(text, pos)
        spans[path] = text[pos:end]
        cursor = space(pos + 1)
        if isinstance(value, dict):
            for key in value:
                _, key_end = decoder.raw_decode(text, cursor)
                cursor = space(key_end) + 1  # colon, already checked by decoder
                _, cursor = walk(cursor, path + (key,))
                cursor = space(cursor)
                cursor = space(cursor + 1)  # comma or closing brace
        elif isinstance(value, list):
            for i in range(len(value)):
                _, cursor = walk(cursor, path + (i,))
                cursor = space(space(cursor) + 1)
        return value, end

    value, end = walk(0, ())
    if space(end) != len(text):
        raise ValueError('trailing non-JSON data')
    return value, spans


def _pointer(path):
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in path)


class EvidenceSession:
    def __init__(self, bug_id, *, run_id=None):
        if not isinstance(bug_id, str) or not bug_id.strip() or len(bug_id) > 200:
            raise ValueError('bug_id must be a nonempty string up to 200 characters')
        self.bug_id = bug_id
        self.run_id = run_id or secrets.token_hex(12)
        self._observations, self._summaries, self._evidence, self._resources = {}, {}, {}, {}
        self._mode = None

    def _resource(self, resource):
        for key, value in self._resources.items():
            if value == resource:
                return key
        key = f'{self.run_id}:R{len(self._resources) + 1}'
        self._resources[key] = deepcopy(resource)
        return key

    def _context(self, oid):
        obs = self._observations[oid]
        if not obs['result'].strip():
            return
        eid = f'{self.run_id}:E{len(self._evidence) + 1}'
        self._evidence[eid] = dict(id=eid, observation_id=oid, resource_id=None, resource=None,
                                  evidence_role='context', source=obs['tool'], quote=obs['result'],
                                  path='', context={}, mode=self._mode)
        self._summaries[oid]['evidence_refs'].append(eid)

    def record(self, observation):
        if len(self._observations) >= 256:
            raise ValueError('observation limit reached; start a new investigation')
        obs = deepcopy(observation)
        oid = f'{self.run_id}:O{len(self._observations) + 1}'
        self._observations[oid] = obs
        summary = {k: deepcopy(obs[k]) for k in ('tool', 'args', 'status', 'observed_at', 'mcp') if k in obs}
        summary.update(observation_id=oid, evidence_refs=[])
        self._summaries[oid] = summary
        mcp = obs.get('mcp', {})
        raw = obs.get('result')
        if (obs.get('status') != 'ok' or not isinstance(raw, str)
                or tool_result_failed(obs.get('tool', ''), raw) or mcp.get('is_error')):
            summary.update(status='error', availability='source_error', diagnostic=str(raw)[:1000])
            return oid
        if (mcp.get('server') != 'k8sgpt' or mcp.get('mode') not in ('live', 'replay')
                or obs.get('tool') != 'mcp_k8sgpt_' + str(mcp.get('tool')).replace('-', '_')):
            summary['availability'] = 'unsupported_provenance'
            return oid
        mode = mcp['mode']
        if self._mode is not None and self._mode != mode:
            summary['availability'] = 'mixed_mode_rejected'
            return oid
        self._mode = mode
        try:
            payload, spans = _json_spans(raw)
        except (ValueError, TypeError, RecursionError):
            summary['availability'] = 'no_structured_evidence'
            self._context(oid)
            return oid
        summary['availability'] = 'empty' if payload in ([], {}) else 'observed'
        namespace = obs.get('args', {}).get('namespace')

        def add(resource, path, role, context=None):
            if not reference(resource) or resource['namespace'] != namespace:
                return
            resource = {k: resource[k] for k in KEYS}
            quote = spans[path]
            eid = f'{self.run_id}:E{len(self._evidence) + 1}'
            rid = self._resource(resource)
            self._evidence[eid] = dict(id=eid, observation_id=oid, resource_id=rid,
                                      resource=deepcopy(resource), evidence_role=role,
                                      source=obs['tool'], quote=quote, path=_pointer(path),
                                      context=deepcopy(context or {}), mode=mode)
            summary['evidence_refs'].append(eid)

        if mcp['tool'] == 'get-resource' and isinstance(payload, dict):
            metadata = payload.get('metadata', {})
            if not isinstance(metadata, dict):
                return oid
            kind = payload.get('kind') or RESOURCE_KINDS.get(obs['args'].get('resourceType'))
            resource = {k: metadata.get(k) for k in KEYS}
            resource['kind'] = kind
            if obs['args'].get('name') != resource['name']:
                return oid
            spec = payload.get('spec')
            if isinstance(spec, dict):
                def configuration(value, path):
                    # Go escapes HTML characters; the existing validator may not
                    # accept the whole spec. Descend into original subtrees, never
                    # rewrite a quote or weaken the validator's matching rules.
                    if quoted(spans[path], spec):
                        add(resource, path, 'configuration')
                    elif isinstance(value, (dict, list)):
                        children = value.items() if isinstance(value, dict) else enumerate(value)
                        for key, child in children:
                            configuration(child, path + (key,))
                    else:
                        summary.setdefault('uncitable_paths', []).append(_pointer(path))
                configuration(spec, ('spec',))
            if isinstance(payload.get('status'), dict):
                add(resource, ('status',), 'context')
        elif mcp['tool'] == 'list-events':
            events = payload.get('items', []) if isinstance(payload, dict) else payload
            base = ('items',) if isinstance(payload, dict) else ()
            if isinstance(events, list):
                for i, event in enumerate(events):
                    if not isinstance(event, dict):
                        continue
                    message = event.get('message')
                    if event.get('type') == 'Warning' and isinstance(message, str) and message.strip():
                        if not quoted(spans[base + (i, 'message')], {'message': message}):
                            summary.setdefault('uncitable_paths', []).append(_pointer(base + (i, 'message')))
                            continue
                        context = {k: event[k] for k in ('type', 'reason', 'firstTimestamp', 'lastTimestamp',
                                                        'eventTime', 'count', 'series') if k in event}
                        add(event.get('involvedObject'), base + (i, 'message'), 'symptom', context)
        if not summary['evidence_refs'] and payload not in ([], {}):
            self._context(oid)
        return oid

    def catalog(self):
        return deepcopy(dict(investigation_id=self.run_id, bug_id=self.bug_id, mode=self._mode,
                             resources=[dict(id=k, **v) for k, v in self._resources.items()],
                             observations=list(self._summaries.values()), evidence=list(self._evidence.values()),
                             collection_gaps=collection_gaps(self._observations.values())))

    def get(self, evidence_id):
        if not isinstance(evidence_id, str) or evidence_id not in self._evidence:
            raise ValueError('unknown evidence reference for this investigation')
        entry = self._evidence[evidence_id]
        return deepcopy(dict(evidence=entry, observation=self._observations[entry['observation_id']]))

    def read(self, evidence_id, full_observation=False):
        detail = self.get(evidence_id)
        if not full_observation:
            # A Pod can supply many references. Do not repeat its full response
            # for every fragment when the model inspects them in one tool batch.
            detail['observation'].pop('result', None)
            detail['full_observation_available'] = True
        return detail

    def _compile(self, draft):
        if not isinstance(draft, dict):
            raise ValueError('verdict draft must be an object')
        if draft.get('investigation_type') != 'infrastructure':
            raise ValueError('reference contract currently supports infrastructure only')
        if draft.get('bug_id') != self.bug_id:
            raise ValueError('bug_id does not match this investigation')
        if any(k in draft for k in ('tool_observations', 'culprit_resources', 'evidence_catalog')):
            raise ValueError('observations/resources are runtime-owned; use culprit_resource_refs')
        refs = draft.get('culprit_resource_refs')
        if not isinstance(refs, list) or not all(isinstance(r, str) and r in self._resources for r in refs):
            raise ValueError('unknown or invalid culprit_resource_refs for this investigation')
        entries = draft.get('evidence')
        if not isinstance(entries, list):
            raise ValueError('evidence must be a list')
        result = deepcopy(draft)
        result['culprit_resources'] = [deepcopy(self._resources[r]) for r in refs]
        expanded = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'claim', 'kind', 'evidence_refs'}:
                raise ValueError('evidence entries require only claim, kind, evidence_refs')
            references = entry['evidence_refs']
            if not isinstance(references, list) or not references or not all(
                    isinstance(r, str) and r in self._evidence for r in references):
                raise ValueError('unknown or empty evidence_refs for this investigation: each entry must cite '
                                 'existing evidence[].id, never observation_id. If the catalog has no evidence, '
                                 'return evidence=[] (no entries), not entries with evidence_refs=[]. '
                                 'Describe source errors and empty queries in limitations. '
                                 'If evidence exists, select the relevant IDs from the catalog.')
            for ref in references:
                fact = self._evidence[ref]
                expanded.append(dict(claim=entry['claim'], kind=entry['kind'], evidence_ref=ref,
                                     source=fact['source'], quote=fact['quote'], resource=deepcopy(fact['resource']),
                                     evidence_role=fact['evidence_role']))
        result['evidence'] = expanded
        result['tool_observations'] = deepcopy(list(self._observations.values()))
        result['evidence_catalog'] = self.catalog()
        return result

    def validate(self, draft):
        try:
            result = self._compile(draft)
        except ValueError as exc:
            return dict(valid=False, errors=[str(exc)], verdict=None)
        errors = validate_verdict(result, expected_bug_id=self.bug_id)
        response = dict(valid=not errors, errors=errors, verdict=result if not errors else None)
        if errors:
            selected = {r for e in draft['evidence'] for r in e['evidence_refs']}
            response['selection_help'] = {
                rid: {role: {
                    'available_refs': [e['id'] for e in self._evidence.values()
                                       if e['resource_id'] == rid and e['evidence_role'] == role],
                    'selected_refs': [e['id'] for e in self._evidence.values()
                                      if e['resource_id'] == rid and e['evidence_role'] == role and e['id'] in selected],
                } for role in ('configuration', 'symptom')}
                for rid in draft['culprit_resource_refs']
            }
        return response
