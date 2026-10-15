"""Native MCP adapter for the same runtime-owned evidence sessions as Python."""
from datetime import datetime, timezone
import json

from jsonschema import Draft202012Validator
from mcp import types

from harness.evidence import EvidenceSession
from harness.mcp_client import response_result, tool_alias
from harness.tool_result import ToolResult


def _tool(name, description, properties, required):
    return types.Tool(name=name, description=description, inputSchema=dict(
        type='object', properties=properties, required=required, additionalProperties=False))


class EvidenceGateway:
    def __init__(self, upstream):
        self.upstream = upstream
        self.sessions = {}
        session = {'investigation_id': {'type':'string'}}
        self.tools = [
            _tool('qai_begin', 'Start an infrastructure investigation; share its ID between roles. No cluster access.',
                  {'bug_id':{'type':'string','minLength':1,'maxLength':200}}, ['bug_id']),
            _tool('qai_observe', 'Call a discovered read-only k8sgpt tool and register its real response. Use raw tool schemas for arguments.',
                  {**session, 'tool':{'type':'string','enum':[t.name for t in upstream.tools]},
                   'arguments':{'type':'object'}}, ['investigation_id','tool','arguments']),
            _tool('qai_catalog', 'Get immutable evidence/resource references and source availability for this investigation.',
                  session, ['investigation_id']),
            _tool('qai_evidence_get', 'Read exact selected fragment and metadata. Set full_observation=true only when the entire original response is needed; avoid repeating it for sibling references.',
                  {**session,'evidence_id':{'type':'string'},'full_observation':{'type':'boolean','default':False}}, ['investigation_id','evidence_id']),
            _tool('qai_validate', 'Compile a reference draft and run the unchanged verdict validator. Only valid=true confirms acceptance.',
                  {**session,'draft':{'type':'object'}}, ['investigation_id','draft']),
        ]
        self.schemas = {t.name:t.inputSchema for t in self.tools}

    async def call(self, name, arguments):
        Draft202012Validator(self.schemas[name]).validate(arguments)
        is_error = False
        if name == 'qai_begin':
            if len(self.sessions) >= 32:
                raise ValueError('session limit reached; reconnect gateway')
            session = EvidenceSession(arguments['bug_id'])
            self.sessions[session.run_id] = session
            value = session.catalog()
        else:
            session = self.sessions.get(arguments['investigation_id'])
            if session is None:
                raise ValueError('unknown investigation_id; reconnect requires a new investigation')
            if name == 'qai_catalog':
                value = session.catalog()
            elif name == 'qai_evidence_get':
                value = session.read(arguments['evidence_id'], arguments.get('full_observation', False))
            elif name == 'qai_validate':
                value = session.validate(arguments['draft'])
                is_error = not value['valid']
            else:
                tool, args = arguments['tool'], arguments['arguments']
                metadata = {'mcp':{'server':'k8sgpt','tool':tool,'transport':'stdio',
                                  'mode':self.upstream.config['mode'],'server_info':self.upstream.server_info},
                            'observed_at':datetime.now(timezone.utc).isoformat()}
                effective = args
                try:
                    response, effective = await self.upstream.call(tool, args)
                    result = response_result(response, metadata)
                except Exception as exc:
                    result = ToolResult(f'MCP ERROR: {type(exc).__name__}: {exc}', True, metadata)
                is_error = result.is_error
                obs = dict(tool=tool_alias(tool), args=effective, result=result.text,
                           status='error' if is_error else 'ok', **metadata)
                oid = session.record(obs)
                value = dict(observation_id=oid, status=obs['status'], result=result.text,
                             catalog=session.catalog())
        return types.CallToolResult(isError=is_error, content=[types.TextContent(type='text', text=json.dumps(value, ensure_ascii=False))])
