"""Сердце воркшопа: агентный цикл в ~40 строк.

Агент = LLM + инструменты + цикл:
  1) отправляем LLM историю сообщений и список доступных инструментов;
  2) если LLM вернула tool_calls — выполняем функции и кладём результаты
     обратно в историю;
  3) повторяем, пока LLM не ответит обычным текстом (или не кончится лимит).
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
MODEL = os.getenv("MODEL", "gpt-4o-mini")

MAX_STEPS = 15


def run_agent(name: str, system_prompt: str, task: str,
              tools_schema: list, tools_impl: dict) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    for step in range(1, MAX_STEPS + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools_schema,
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            # Инструменты не нужны — агент сформулировал финальный ответ
            return msg.content

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            print(f"  [{name}] шаг {step}: {call.function.name}({args})")
            try:
                result = tools_impl[call.function.name](**args)
            except Exception as exc:
                result = f"ОШИБКА ИНСТРУМЕНТА: {exc}"
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            })

    return "Лимит шагов исчерпан. Промежуточные выводы: " + str(messages[-1])
