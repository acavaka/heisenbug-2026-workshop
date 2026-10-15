#!/usr/bin/env python3
"""Read-only application evidence MCP. Replay is isolated; live must be explicit."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from jsonschema import Draft202012Validator
from harness.application_session import ApplicationSession
from harness.evidence_mcp import _tool
from harness.verdict import tool_result_failed


def verdict_schema():
    strings = {'type':'array','items':{'type':'string'}}
    properties = {k:{'type':'string'} for k in ('bug_id','root_cause','fix_direction')}
    properties.update({k:strings for k in ('culprit_files','reasons','false_leads','limitations')})
    properties.update(investigation_type={'type':'string','enum':['application']},
        confidence={'type':'string','enum':['low','medium','high']},
        red_team={**strings,'minItems':3,'maxItems':3},
        evidence={'type':'array','items':{'type':'object','properties':{
            'claim':{'type':'string','description':'Observed fact or explicitly marked inference. A code FACT must describe the actual quoted code; separate its causal interpretation.'},
            'kind':{'type':'string','enum':['ФАКТ','ВЫВОД','ГИПОТЕЗА']},
            'evidence_ref':{'type':'string','description':'Exact ID from this investigation catalog. Empty only for inference/hypothesis without a quote.'}},
            'required':['claim','kind','evidence_ref'],'additionalProperties':False}})
    properties['culprit_files']={**strings,'description':'file:line from observed_file_lines, supported by a ФАКТ quoting that exact code line.'}
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)


class ApplicationGateway:
    def __init__(self, backend_factory):
        self.factory = backend_factory
        self.sessions = {}
        sid = {'investigation_id': {'type':'string'}}
        self.tools = [
            _tool('qai_begin','Start application investigation. All observations must use qai_observe.',
                  {'bug_id':{'type':'string','minLength':1,'maxLength':200}},['bug_id']),
            _tool('qai_catalog','Return runtime evidence, available tool schemas, scope and correlation state.',sid,['investigation_id']),
            _tool('qai_observe','Execute an available read-only tool; register its actual output. Arguments follow catalog schemas.',
                  {**sid,'tool':{'type':'string'},'arguments':{'type':'object'}},['investigation_id','tool','arguments']),
            _tool('qai_evidence_get','Read exact evidence. References belong to this investigation only.',
                  {**sid,'evidence_id':{'type':'string'},'full_observation':{'type':'boolean'}},['investigation_id','evidence_id']),
            _tool('qai_validate','Expand evidence_ref and validate the ordinary application verdict with the shared full validator. Required fields: bug_id, investigation_type=application, root_cause, culprit_files, confidence, reasons, evidence[{claim,kind,evidence_ref}], false_leads, red_team, limitations, fix_direction. Only valid=true confirms acceptance.',
                  {**sid,'draft':verdict_schema()},['investigation_id','draft']),
        ]
        self.schemas = {t.name:t.inputSchema for t in self.tools}

    def catalog(self, session, backend):
        schemas, _ = backend.available()
        return {**session.catalog(), 'tools':schemas, **backend.context()}

    async def call(self, name, args):
        Draft202012Validator(self.schemas[name]).validate(args)
        error = False
        if name == 'qai_begin':
            if len(self.sessions) >= 32:
                raise ValueError('session limit reached; reconnect')
            backend = self.factory(args['bug_id'])
            session = ApplicationSession(args['bug_id'])
            self.sessions[session.run_id] = session, backend
            value = self.catalog(session, backend)
        else:
            if args['investigation_id'] not in self.sessions:
                raise ValueError('unknown investigation_id')
            session, backend = self.sessions[args['investigation_id']]
            if name == 'qai_catalog':
                value = self.catalog(session, backend)
            elif name == 'qai_evidence_get':
                value = session.read(args['evidence_id'],args.get('full_observation',False))
            elif name == 'qai_validate':
                value = session.validate(args['draft'])
                context = backend.context()
                gate = context.get('correlation')
                if context['mode'] == 'synthetic_file_replay' and not (gate and gate['rca_allowed']) and (args['draft'].get('root_cause') or args['draft'].get('culprit_files') or args['draft'].get('confidence') != 'low'):
                    value = dict(valid=False,errors=['correlation gate requires abstention'],verdict=None)
                error = not value['valid']
            else:
                schemas, impl = backend.available()
                tool = args['tool']
                if tool not in impl:
                    raise ValueError('tool unavailable or blocked by correlation gate')
                schema = next(s['function']['parameters'] for s in schemas if s['function']['name']==tool)
                Draft202012Validator(schema).validate(args['arguments'])
                try:
                    result = str(impl[tool](**args['arguments']))
                except Exception as exc:
                    result = f'TOOL ERROR: {type(exc).__name__}: {exc}'
                error = tool_result_failed(tool,result)
                oid = session.record(dict(tool=tool,args=args['arguments'],result=result,status='error' if error else 'ok'))
                value = dict(observation_id=oid,result=result,catalog=self.catalog(session,backend))
        return types.CallToolResult(isError=error,content=[types.TextContent(type='text',text=json.dumps(value,ensure_ascii=False))])


class ReplayTools:
    def __init__(self, bug_id, case):
        if bug_id != 'BUG-LAB-01':
            raise ValueError('Only BUG-LAB-01 is available in replay')
        from exercises.trace_to_logs.orchestrator_replay import ReplayBackend
        from skills.trace_logs import correlate
        self.backend = ReplayBackend(case,correlate)

    def available(self):
        schemas, impl = [], {}
        roles = ['qai-report-analyzer','qai-data-investigator']
        if self.backend.correlation and self.backend.correlation['rca_allowed']:
            roles.append('qai-hypothesis-checker')
        for role in roles:
            s,i = self.backend.tools(role); schemas += s; impl.update(i)
        return schemas,impl

    def context(self):
        return dict(mode='synthetic_file_replay',case=self.backend.case,correlation=self.backend.correlation)


class LiveTools:
    def __init__(self, bug_id):
        pass

    def available(self):
        from skills import ALL_TOOLS_SCHEMA, ALL_TOOLS_IMPL
        # Explicit read-only subset; no arbitrary SQL, runbook, shell or MCP fallback.
        allowed = {'tracker_list','tracker_get','wiki_get','testops_get','github_release_notes',
                   'kubectl_get_pods','kubectl_logs','grep_pod_logs','tempo_search','tempo_get_trace',
                   'trace_to_logs','temporal_inspect','prom_query','code_search','read_file'}
        schemas = [s for s in ALL_TOOLS_SCHEMA if s['function']['name'] in allowed]
        return schemas,{s['function']['name']:ALL_TOOLS_IMPL[s['function']['name']] for s in schemas}

    def context(self):
        return dict(mode='live_read_only')


async def serve(factory):
    gateway = ApplicationGateway(factory)
    server = Server('qai-application')
    @server.list_tools()
    async def list_tools():
        return gateway.tools
    @server.call_tool()
    async def call_tool(name, arguments):
        try:
            return await gateway.call(name,arguments)
        except Exception as exc:
            return types.CallToolResult(isError=True,content=[types.TextContent(type='text',text=f'MCP ERROR: {type(exc).__name__}: {exc}')])
    async with stdio_server() as (read,write):
        await server.run(read,write,server.create_initialization_options())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['replay','live'],default='replay')
    parser.add_argument('--case',choices=['complete','missing-logs','incomplete-trace','no-ids','invalid-trace'],default='complete')
    args=parser.parse_args()
    os.environ['QAI_READ_ONLY']='1'
    if args.mode=='replay':
        os.environ['BOUTIQUE_ROOT']=str(Path(__file__).resolve().parents[1]/'fixtures/trace-to-logs/business-checkout/code')
        os.environ['ORDER_WORKER_ROOT']=str(Path(__file__).parent/'.no-order-worker')
        factory=lambda bug:ReplayTools(bug,args.case)
    else:
        factory=LiveTools
    asyncio.run(serve(factory))

if __name__=='__main__':
    main()
