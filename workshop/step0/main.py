"""ШАГ 0. «Hello, LLM» — точка старта.

Здесь ещё нет никакого агента: один запрос — один ответ.
Убеждаемся, что все понимают три вещи:
  1) как устроен запрос (system + user сообщения);
  2) что такое system prompt и как он меняет поведение;
  3) что модель без инструментов НЕ видит наши файлы и логи.

Запуск: python step0/main.py
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
MODEL = os.getenv("MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Ты — QA-инженер, расследующий баги.
Отвечай кратко и по делу, на русском языке."""

question = "В логах видно cache hit со старой ценой после её обновления. Какие гипотезы?"

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ],
)

print(response.choices[0].message.content)

# УПРАЖНЕНИЕ 1: поменяйте system prompt (например, «отвечай как пират»)
#   и посмотрите, как меняется ответ.
# УПРАЖНЕНИЕ 2: спросите модель, что лежит в файле fixtures/logs/app-2026-06-16.log.
#   Она не знает — и это главная проблема, которую решают инструменты (шаг 2).
