"""Общий агентный цикл (DIY harness).

Агент = LLM + инструменты + цикл:
  1) messages + tools → LLM
  2) tool_calls → execute → append
  3) пока нет tool_calls или max_steps

API-путь использует OpenAI-совместимый endpoint (OPENAI_BASE_URL); strict tool calling
нужен модельному оркестратору. QAI_LLM_TRANSPORT=codex выбирает отдельный транспорт
Codex по подписке для поддерживаемого replay-пути. Модель на роль:
MODEL_FAST для дешёвых ролей (разбор репорта, вердикт), MODEL_STRONG для
расследования и кода; обе по умолчанию равны MODEL.

Устойчивость к залу: клиент сам ретраит 429/5xx с backoff (LLM_MAX_RETRIES),
таймаут на запрос LLM_TIMEOUT_S. Каждый вызов LLM и инструмента пишется в
трейс прогона (harness/trace.py): JSONL + спаны в Tempo.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI

from harness import trace
from harness.prompts import load_prompt
from harness.verdict import tool_result_failed
from harness.tool_result import ToolResult

CODEX_TRANSPORT = os.getenv('QAI_LLM_TRANSPORT') == 'codex'
if not CODEX_TRANSPORT:
    load_dotenv()

client = None if CODEX_TRANSPORT else OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    max_retries=int(os.getenv("LLM_MAX_RETRIES", "6")),
    timeout=float(os.getenv("LLM_TIMEOUT_S", "120")),
)
MODEL = os.getenv("MODEL", "gpt-4o-mini")
MODELS = {
    "fast": os.getenv("MODEL_FAST", MODEL),
    "strong": os.getenv("MODEL_STRONG", MODEL),
}
MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))
MAX_TOOL_CHARS = int(os.getenv("MAX_TOOL_CHARS", "8000"))


def _structured_tool(name: str) -> bool:
    return name.startswith("mcp_k8sgpt_") or name == "qai_evidence_get"


def _truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_CHARS:
        return text
    return text[:MAX_TOOL_CHARS] + f"\n... truncated ({len(text)} chars total)"


def _tool_message(name: str, text: str) -> str:
    """JSON is an atomic document; never turn it into a sliced text fragment.

    Tools must bound queries/results structurally. A large JSON document is kept
    whole here; pagination or a referenced artifact belongs to the source tool.
    """
    if _structured_tool(name):
        return text
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return _truncate(text)
    return text if isinstance(value, (dict, list)) else _truncate(text)


def _llm(model: str, messages: list, tools_schema: list, step: int):
    if CODEX_TRANSPORT:
        from harness.codex_transport import decision
        return decision(model, messages, tools_schema, step)
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if tools_schema:
        kwargs["tools"] = tools_schema
        if any(tool.get('function', {}).get('strict') is True for tool in tools_schema):
            # The orchestrator must observe a delegation/type change before
            # deciding the next action or submitting against its updated schema.
            kwargs['parallel_tool_calls'] = False
    with trace.span("llm.call", model=model, step=step, messages=len(messages)) as attrs:
        response = client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage and trace.current():
            trace.current().usage(usage.prompt_tokens or 0, usage.completion_tokens or 0)
            attrs["tokens_in"], attrs["tokens_out"] = usage.prompt_tokens, usage.completion_tokens
        msg = response.choices[0].message
        attrs["tool_calls"] = len(msg.tool_calls or [])
        return msg


def _call_tool(name: str, impl: Callable | None, args: dict, role: str, *, argument_error: str | None = None) -> str:
    with trace.span("tool.call", tool=name, args=args, role=role) as attrs:
        metadata, protocol_error = {}, False
        try:
            if argument_error:
                result = f"TOOL ERROR: invalid arguments: {argument_error}"
            elif impl is None:
                result = f"ERROR: unknown tool {name}"
            else:
                value = impl(**args)
                if isinstance(value, ToolResult):
                    metadata, protocol_error = value.metadata, value.is_error
                result = str(value)
        except Exception as exc:  # noqa: BLE001 — feedback to model
            result = f"TOOL ERROR: {exc}"
        attrs["result_chars"] = len(result)
        attrs["result_preview"] = result[:300]
        failed = protocol_error or tool_result_failed(name, result)
        attrs["tool_error"] = failed
        run = trace.current()
        if run:
            run.tool_calls += 1
            run.tool_observations.append({
                **{k: v for k, v in metadata.items() if k in {"mcp", "observed_at"}},
                "tool": name, "args": dict(metadata.get("effective_args", args)),
                "result": result, "role": role,
                "status": "error" if failed else "ok",
            })
        return result


def run_agent(
    name: str,
    system_prompt: str,
    task: str,
    tools_schema: list[dict[str, Any]],
    tools_impl: dict[str, Callable[..., Any]],
    model: str | None = None,
    max_steps: int | None = None,
    stop_when: Callable[[], bool] | None = None,
    required_final_tool: str | None = None,
    abort_when: Callable[[], bool] | None = None,
) -> str:
    model = model or MODEL
    max_steps = max_steps or MAX_STEPS
    messages: list[Any] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    with trace.span("role", name=name, model=model, max_steps=max_steps) as role_attrs:
        for step in range(1, max_steps + 1):
            msg = _llm(model, messages, tools_schema, step)
            messages.append(msg)

            if not msg.tool_calls:
                if required_final_tool and stop_when is not None and not stop_when():
                    messages.append({"role": "user", "content": (
                        f"Runtime has not accepted a verdict. Text is not a submission. "
                        f"Address the tool errors using actual observations, then call {required_final_tool}. "
                        "Do not invent missing evidence. The existing step and submission budgets still apply."
                    )})
                    continue
                role_attrs["steps"] = step
                role_attrs["answer_chars"] = len(msg.content or "")
                return msg.content or ""

            for call in msg.tool_calls:
                argument_error = None
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                except (ValueError, TypeError) as exc:
                    args = {}
                    argument_error = str(exc)
                print(f"  [{name}] step {step}: {call.function.name}({args})")
                result = _call_tool(call.function.name, tools_impl.get(call.function.name), args, name,
                                    argument_error=argument_error)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _tool_message(call.function.name, result),
                })
                if stop_when is not None and stop_when():
                    role_attrs["steps"] = step
                    role_attrs["runtime_accepted"] = True
                    return result
                if abort_when is not None and abort_when():
                    role_attrs["steps"] = step
                    role_attrs["runtime_aborted"] = True
                    return result

        role_attrs["steps"] = max_steps
        role_attrs["step_limit"] = True
        return "Step limit reached. Last message: " + str(messages[-1])


def run_role(role: str, task: str, tools_schema: list, tools_impl: dict) -> str:
    """Запустить роль из prompts/<role>.md: промпт, класс модели и max_steps берутся из файла."""
    prompt = load_prompt(role)
    return run_agent(role, prompt.body, task, tools_schema, tools_impl, MODELS[prompt.model], prompt.max_steps)


__all__ = ["run_agent", "run_role", "MODEL", "MODELS"]
