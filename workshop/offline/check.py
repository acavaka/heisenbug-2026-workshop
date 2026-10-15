#!/usr/bin/env python3
"""No-model, no-live-stand startup checks of an extracted participant kit."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['OPENAI_API_KEY']='';os.environ['AGENT_TRACES']='0'
for name in ('QAI_MCP_CONFIG','QAI_KUBECONFIG'):os.environ.pop(name,None)
os.chdir(ROOT)

def run(args,expected=0):
 r=subprocess.run([sys.executable,*args],capture_output=True,text=True)
 if r.returncode!=expected:raise RuntimeError(f'{args}: exit {r.returncode}: {r.stderr[:1000]} {r.stdout[:1000]}')
 return r.stdout

async def mcp_check():
 from mcp import ClientSession,StdioServerParameters
 from mcp.client.stdio import stdio_client
 params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'workshop/application_mcp.py'),'--mode','replay','--case','complete'])
 async with stdio_client(params) as (read,write):
  async with ClientSession(read,write) as session:
   await session.initialize();tools=await session.list_tools()
   assert {t.name for t in tools.tools}=={'qai_begin','qai_observe','qai_catalog','qai_evidence_get','qai_validate'}
   result=await session.call_tool('qai_begin',{'bug_id':'BUG-LAB-01'})
   begin=json.loads(result.content[0].text);sid=begin['investigation_id']
   result=await session.call_tool('qai_catalog',{'investigation_id':sid});cat=json.loads(result.content[0].text)
   assert not cat.get('evidence'),cat
 print('application MCP: five tools, begin and empty catalog OK')

run(['-m','pip','check'])
run(['workshop/qai_tool.py','--read-only','--list'])
assert 'BUG-1024' in run(['workshop/qai_tool.py','--read-only','tracker_get','bug_id=BUG-1024'])
source=run(['workshop/qai_tool.py','--read-only','read_file','path=workshop/services/order-worker/workflows.py'])
assert 'TOOL ERROR' not in source and len(source)>100,source
for name in ('report','pods'):run(['workshop/exercises/trace_to_logs/run.py',name])
assert 'false' in run(['workshop/exercises/trace_to_logs/run.py','check'],expected=1).lower()
run(['workshop/mcp_check.py','--config','workshop/mcp/replay.json','--probe-replay'])
run(['workshop/e2e.py','--help'])
asyncio.run(mcp_check())
print('PASS: dependencies, registry, tracker, worker source, file replay, expected TODO failure, both MCP handshakes. No model/API/live cluster called.')
