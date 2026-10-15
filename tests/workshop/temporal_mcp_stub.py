"""Production MCP with a synthetic Temporal client; never connects to a cluster."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workshop"))
from temporalio.client import Client
from temporalio.api.history.v1 import HistoryEvent
from application_mcp import LiveTools, serve

RUN = "00000000-0000-4000-8000-000000000001"


class Page:
    def __init__(self, rows, token=b""):
        self.current_page, self.next_page_token = rows, token

    async def fetch_next_page(self):
        await asyncio.sleep(0)


class ReadOnlyTemporal:
    def list_workflows(self, query, **kwargs):
        if query == "synthetic failure":
            raise RuntimeError("synthetic source unavailable")
        return Page([]) if kwargs["next_page_token"] else Page([self.execution()], b"page-two")

    def execution(self):
        return SimpleNamespace(id="synthetic-order", run_id=RUN, status=SimpleNamespace(name="RUNNING"),
                               workflow_type="SyntheticFlow", start_time=None)

    def get_workflow_handle(self, workflow_id, run_id=None):
        assert workflow_id == "synthetic-order" and run_id in (None, RUN)
        return self

    async def describe(self, **kwargs):
        await asyncio.sleep(0)
        return self.execution()

    def fetch_history_events(self, **kwargs):
        assert kwargs["wait_new_event"] is False
        return Page([HistoryEvent(event_id=1, event_type=1)])


async def connect(*args, **kwargs):
    assert kwargs["namespace"] == "synthetic-only"
    return ReadOnlyTemporal()


if __name__ == "__main__":
    Client.connect = connect
    asyncio.run(serve(LiveTools))
