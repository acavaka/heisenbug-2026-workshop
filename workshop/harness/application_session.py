"""Runtime-owned application observations for editor MCP clients.

Uses the same reference compiler and complete verdict validator as Python.
No model, source access, or inference of claims lives in this class.
"""
from copy import deepcopy
from uuid import uuid4
from harness.application_evidence import catalog, expand
from harness.verdict import validate_verdict, tool_result_failed


class ApplicationSession:
    def __init__(self, bug_id):
        self.bug_id = bug_id
        self.run_id = uuid4().hex
        self._observations = []

    def record(self, observation):
        obs = deepcopy(observation)
        if tool_result_failed(obs['tool'], obs['result']):
            obs['status'] = 'error'
        self._observations.append(obs)
        return f'{self.run_id}:A{len(self._observations)}'

    def catalog(self):
        return dict(investigation_id=self.run_id, bug_id=self.bug_id,
                    investigation_type='application',
                    **catalog(self._observations, self.run_id))

    def read(self, evidence_id, full_observation=False):
        for entry in self.catalog()['evidence']:
            if entry['id'] == evidence_id:
                index = int(evidence_id.split(':A')[1].split('L')[0]) - 1
                obs = deepcopy(self._observations[index])
                if not full_observation:
                    obs.pop('result', None)
                return dict(evidence=entry, observation=obs)
        raise ValueError('unknown evidence reference for this investigation')

    def validate(self, draft):
        errors = []
        if not isinstance(draft, dict):
            errors.append('draft must be an object')
        elif draft.get('bug_id') != self.bug_id or draft.get('investigation_type') != 'application':
            errors.append('bug_id and application profile must match this investigation')
        elif any(k in draft for k in ('tool_observations', 'evidence_catalog')):
            errors.append('observations and catalog are runtime-owned')
        if errors:
            return dict(valid=False, errors=errors, verdict=None)
        result, errors = expand(draft, self.catalog())
        result['tool_observations'] = deepcopy(self._observations)
        errors += validate_verdict(result, expected_bug_id=self.bug_id)
        return dict(valid=not errors, errors=errors, verdict=result if not errors else None)
