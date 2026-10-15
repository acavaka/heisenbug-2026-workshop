"""Проверка окружения перед воркшопом. Запуск: python smoke_test.py

Проверяет: версию Python, зависимости, .env, доступность LLM и tool calling.
"""

import json
import sys


def fail(msg: str) -> None:
    print(f"  FAIL: {msg}")
    sys.exit(1)


print("1. Python...", end=" ")
if sys.version_info < (3, 10):
    fail(f"нужен Python 3.10+, у вас {sys.version.split()[0]}")
print(f"OK ({sys.version.split()[0]})")

print("2. Зависимости...", end=" ")
try:
    import dotenv  # noqa: F401
    from openai import OpenAI
except ImportError as exc:
    fail(f"{exc}. Выполните: pip install -r requirements.txt")
print("OK")

print("3. Конфигурация...", end=" ")
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    fail("нет OPENAI_API_KEY. Скопируйте .env.example в .env и впишите ключ")
model = os.getenv("MODEL", "gpt-4o-mini")
print(f"OK (model={model}, base_url={os.getenv('OPENAI_BASE_URL') or 'по умолчанию'})")

ROOT = Path(__file__).resolve().parent
print("3a. Логи для шагов 0-2...", end=" ")
logs_dir = ROOT.parent / "fixtures" / "logs"
if not any(logs_dir.glob("*.log")):
    subprocess.run([sys.executable, str(ROOT.parent / "fixtures" / "generate_logs.py")], check=True)
    print("сгенерированы", end=" ")
print(f"OK ({len(list(logs_dir.glob('*.log')))} файлов)")

print("3b. BOUTIQUE_ROOT...", end=" ")
boutique = Path(os.getenv("BOUTIQUE_ROOT", ROOT.parent / "microservices-demo"))
if not (boutique / "src").exists():
    fail(f"{boutique} не содержит src/. В .env укажите BOUTIQUE_ROOT=<репо>/microservices-demo")
print(f"OK ({boutique})")

client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)

print("4. Запрос к LLM...", end=" ")
try:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Ответь одним словом: работает?"}],
    )
except Exception as exc:
    fail(f"{exc}")
print(f"OK (ответ: {resp.choices[0].message.content!r})")

print("5. Tool calling...", end=" ")
tools = [{
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Проверка связи",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
}]
try:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Вызови инструмент ping с message='hello'"}],
        tools=tools,
    )
except Exception as exc:
    fail(f"{exc}")
calls = resp.choices[0].message.tool_calls
if not calls:
    fail("модель не вызвала инструмент — tool calling не работает, скажите ведущему")
args = json.loads(calls[0].function.arguments)
print(f"OK (модель вызвала {calls[0].function.name}({args}))")

print("\nВсё готово к воркшопу!")
