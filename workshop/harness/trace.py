"""Наблюдаемость самого агента: JSONL-лог прогона + спаны в Tempo.

Зачем: неверный вердикт нечем разбирать, если не видно, какие инструменты
агент вызывал, что получил и сколько это стоило. Каждый прогон пишет
reports/<BUG>.trace.jsonl. Экспорт спанов в Tempo (OTLP/HTTP) выполняется только
при AGENT_TRACES=1 и end_run(export=True). Read-only расследование вызывает
end_run(export=False), сохраняя локальную трассу без записи в стенд.

Иерархия спанов:  investigation(bug_id) → role(name, model) → llm.call / tool.call

Смотреть: Grafana → Explore → Tempo → trace_id из консоли, или TraceQL
  { resource.service.name = "qai-agent" }
"""

from __future__ import annotations

import json
import os
import secrets
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

OTLP_URL = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318").rstrip("/") + "/v1/traces"
AGENT_TRACES = os.getenv("AGENT_TRACES", "1") != "0"
SERVICE_NAME = "qai-agent"
# Цена за 1M токенов, чтобы печатать стоимость прогона. 0 = печатать только токены.
PRICE_IN = float(os.getenv("PRICE_IN_PER_1M", "0"))
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_1M", "0"))
MAX_ATTR_CHARS = 2000


def _now_ns() -> int:
    return time.time_ns()


def _attr(key: str, value: Any) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return {"key": key, "value": {"stringValue": text[:MAX_ATTR_CHARS]}}


@dataclass
class Span:
    name: str
    span_id: str
    parent_id: str | None
    start_ns: int
    attrs: dict[str, Any] = field(default_factory=dict)
    end_ns: int = 0
    error: str | None = None


@dataclass
class Run:
    bug_id: str
    trace_id: str
    log_path: Path
    spans: list[Span] = field(default_factory=list)
    stack: list[Span] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    # Exact bounded tool messages used for verdict citation checks and saved eval.
    tool_observations: list[dict[str, Any]] = field(default_factory=list)
    evidence_session: Any = None
    evidence_observation_count: int = 0

    def event(self, kind: str, **data: Any) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, **data}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def usage(self, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.llm_calls += 1

    def cost(self) -> float:
        return (self.tokens_in * PRICE_IN + self.tokens_out * PRICE_OUT) / 1_000_000

    def summary(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost(), 4) if PRICE_IN or PRICE_OUT else None,
            "log": str(self.log_path),
        }


_current: Run | None = None


def current() -> Run | None:
    return _current


def start_run(bug_id: str, reports_dir: Path) -> Run:
    global _current
    reports_dir.mkdir(parents=True, exist_ok=True)
    log = reports_dir / f"{bug_id}.trace.jsonl"
    log.write_text("", encoding="utf-8")
    _current = Run(bug_id=bug_id, trace_id=secrets.token_hex(16), log_path=log)
    _current.event("run.start", bug_id=bug_id, trace_id=_current.trace_id)
    _open(_current, "investigation", {"bug_id": bug_id})
    return _current


def end_run(*, export: bool = True) -> dict:
    global _current
    run = _current
    if run is None:
        return {}
    while run.stack:
        _close(run, run.stack[-1])
    run.event("run.end", **run.summary())
    exported = _export(run) if export else False
    _current = None
    return {**run.summary(), "exported_to_tempo": exported}


def _open(run: Run, name: str, attrs: dict) -> Span:
    parent = run.stack[-1].span_id if run.stack else None
    span = Span(name=name, span_id=secrets.token_hex(8), parent_id=parent, start_ns=_now_ns(), attrs=dict(attrs))
    run.spans.append(span)
    run.stack.append(span)
    return span


def _close(run: Run, span: Span) -> None:
    span.end_ns = _now_ns()
    if run.stack and run.stack[-1] is span:
        run.stack.pop()


@contextmanager
def span(kind: str, **attrs: Any) -> Iterator[dict]:
    """Спан + JSONL-событие. Тело может дописать атрибуты в возвращённый dict."""
    run = _current
    if run is None:
        yield attrs
        return
    s = _open(run, kind, attrs)
    run.event(f"{kind}.start", **{k: v for k, v in attrs.items() if k != "result"})
    try:
        yield s.attrs
    except Exception as exc:
        s.error = f"{type(exc).__name__}: {exc}"
        s.attrs["error"] = s.error
        raise
    finally:
        _close(run, s)
        run.event(f"{kind}.end", duration_ms=(s.end_ns - s.start_ns) // 1_000_000,
                  **{k: (v if len(str(v)) <= MAX_ATTR_CHARS else str(v)[:MAX_ATTR_CHARS] + "…")
                     for k, v in s.attrs.items() if k not in attrs})


def _export(run: Run) -> bool:
    if not AGENT_TRACES or not run.spans:
        return False
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [_attr("service.name", SERVICE_NAME), _attr("qai.bug_id", run.bug_id)]},
            "scopeSpans": [{
                "scope": {"name": "qai.harness"},
                "spans": [{
                    "traceId": run.trace_id,
                    "spanId": s.span_id,
                    **({"parentSpanId": s.parent_id} if s.parent_id else {}),
                    "name": s.name,
                    "kind": 1,
                    "startTimeUnixNano": str(s.start_ns),
                    "endTimeUnixNano": str(s.end_ns or _now_ns()),
                    "attributes": [_attr(k, v) for k, v in s.attrs.items()],
                    "status": {"code": 2, "message": s.error} if s.error else {"code": 1},
                } for s in run.spans],
            }],
        }]
    }
    req = urllib.request.Request(
        OTLP_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 — стенд может быть не поднят, это не ошибка прогона
        run.event("tempo.export_failed", error=str(exc))
        return False


if __name__ == "__main__":
    import tempfile

    os.environ["AGENT_TRACES"] = "0"
    AGENT_TRACES = False
    with tempfile.TemporaryDirectory() as tmp:
        run = start_run("BUG-TEST", Path(tmp))
        with span("role", name="r1"):
            with span("llm.call", model="m") as a:
                run.usage(100, 20)
                a["tokens_out"] = 20
            with span("tool.call", tool="t", args={"x": 1}) as a:
                a["result_chars"] = 5
        s = end_run()
        assert s["llm_calls"] == 1 and s["tokens_in"] == 100, s
        lines = run.log_path.read_text(encoding="utf-8").splitlines()
        kinds = [json.loads(l)["kind"] for l in lines]
        assert kinds[0] == "run.start" and kinds[-1] == "run.end" and "tool.call.end" in kinds, kinds
        assert len(run.spans) == 4 and run.spans[1].parent_id == run.spans[0].span_id
    print("trace OK")
