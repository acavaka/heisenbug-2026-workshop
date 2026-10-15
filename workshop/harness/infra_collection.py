"""Shared collection checklist, not a diagnosis or verdict validator."""
import json
from harness.infra_verdict import RESOURCE_KINDS


def collection_gaps(observations):
    resources, event_queries, log_queries = {}, [], []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        provenance, args = obs.get('mcp', {}), obs.get('args', {})
        if (not isinstance(provenance, dict) or not isinstance(args, dict)
                or obs.get('status') != 'ok' or provenance.get('is_error')
                or provenance.get('server') != 'k8sgpt'
                or provenance.get('mode') not in ('replay', 'live')):
            continue
        name = provenance.get('tool')
        if obs.get('tool') != 'mcp_k8sgpt_' + str(name).replace('-', '_'):
            continue
        if name == 'get-logs':
            if not args.get('previous'):
                log_queries.append(args)
            continue
        try:
            payload = json.loads(obs.get('result'))
        except (ValueError, TypeError):
            continue
        if name == 'get-resource' and isinstance(payload, dict):
            metadata = payload.get('metadata', {})
            if (isinstance(metadata, dict)
                    and all(isinstance(metadata.get(k), str) and metadata[k] for k in ('uid','namespace','name'))
                    and isinstance(payload.get('spec'), dict) and payload['spec']
                    and metadata.get('namespace') == args.get('namespace')
                    and metadata.get('name') == args.get('name')):
                kind = payload.get('kind') or RESOURCE_KINDS.get(str(args.get('resourceType')))
                resources[(metadata['namespace'], metadata['name'], metadata['uid'])] = {**payload, 'kind':kind}
        elif name == 'list-events':
            values = payload.get('items') if isinstance(payload, dict) else payload
            if isinstance(values, list):
                event_queries.append(args)
    if not resources:
        return [dict(tool=name, arguments={}, reason='Read resource spec/status/UID, then query its events.')
                for name in ('get-resource', 'list-events')]
    gaps = []
    for pod in resources.values():
        metadata = pod['metadata']
        namespace, name, kind = metadata['namespace'], metadata['name'], pod.get('kind')
        if not any(q.get('namespace') == namespace
                   and q.get('involvedObjectName', name) == name
                   and q.get('involvedObjectKind', kind) == kind for q in event_queries):
            gaps.append(dict(tool='list-events', arguments={'namespace':namespace, 'involvedObjectName':name,
                                                           'involvedObjectKind':kind}, reason='Query events for this object; empty is an acceptable response.'))
        if kind != 'Pod':
            continue
        status = pod.get('status')
        containers = status.get('containerStatuses') if isinstance(status, dict) else None
        if not isinstance(containers, list):
            gaps.append(dict(tool='get-resource', arguments={'namespace':namespace,'resourceType':'pods','name':name},
                             reason='Current container status is unavailable or malformed; retry once, then report limitation.'))
            continue
        for container in containers:
            if (not isinstance(container, dict) or not isinstance(container.get('state'), dict)
                    or 'running' not in container['state'] or not isinstance(container.get('name'), str)):
                continue
            container_name = container.get('name')
            if not any(q.get('namespace') == namespace and q.get('podName') == name
                       and (q.get('container') == container_name
                            or (not q.get('container') and len(containers) == 1)) for q in log_queries):
                gaps.append(dict(tool='get-logs', arguments={'namespace':namespace, 'podName':name, 'container':container_name},
                                 reason='Container is running; read logs before concluding about application symptoms.'))
    return gaps
