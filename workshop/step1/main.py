"""ШАГ 1. Агент №1 — qai-report-analyzer: анализ баг-репорта.

Первый специализированный «агент»: system prompt задаёт роль,
structured output (JSON) превращает свободный текст репорта в данные,
с которыми смогут работать следующие агенты.

Запуск: python step1/main.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
MODEL = os.getenv("MODEL", "gpt-4o-mini")

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

REPORT_ANALYZER_PROMPT = """Ты — qai-report-analyzer, агент анализа баг-репортов.

Твоя задача: прочитать баг-репорт и извлечь из него структурированную
информацию для дальнейшего расследования. Ничего не выдумывай: если данных
нет в репорте, оставляй поле пустым.

Ответь СТРОГО в формате JSON:
{
  "summary": "суть проблемы одним предложением",
  "affected_components": ["компоненты/модули, которые могут быть причастны"],
  "symptoms": ["наблюдаемые симптомы"],
  "timeline": ["известные события с временными метками"],
  "reproduction": "как воспроизводится (стабильно/нестабильно и условия)",
  "search_keywords": ["ключевые слова для поиска по логам: id, sku, суммы, имена операций"],
  "priority_directions": ["1-3 приоритетных направления расследования"]
}"""


def analyze_report(bug_id: str) -> dict:
    report_text = (FIXTURES / "tracker" / f"{bug_id}.md").read_text(encoding="utf-8")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPORT_ANALYZER_PROMPT},
            {"role": "user", "content": f"Баг-репорт:\n\n{report_text}"},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


if __name__ == "__main__":
    analysis = analyze_report("BUG-1024")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))

# УПРАЖНЕНИЕ 1: уберите строку про «ничего не выдумывай» из промпта и
#   сравните search_keywords — станет ли агент фантазировать?
# УПРАЖНЕНИЕ 2: добавьте в JSON поле "false_leads" — что в репорте похоже
#   на ложный след (подсказка: промокоды).
