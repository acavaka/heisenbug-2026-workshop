"""ШАГ 2. Агент №2 — qai-log-investigator: исследование логов.

Здесь появляется настоящий агент: LLM сама решает, какие инструменты
вызвать и в каком порядке. Понаблюдайте за печатью шагов: видно, как агент
сужает поиск от симптомов к конкретным строкам лога.

Источник логов выбирается автоматически:
  - кластер kind-qai-boutique доступен → живые логи через kubectl (skills/cluster_logs.py),
    баг BUG-1024 на товаре OLJCESPC7Z (перед этим: ../microservices-demo/hack/reproduce-bug-1024.sh);
  - кластера нет → файловые фикстуры fixtures/logs (tools.py), тот же баг в legacy-варианте SKU-4217.
Принудительно: python step2/main.py --fixtures

Запуск: python step2/main.py
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import run_agent  # noqa: E402

LOG_INVESTIGATOR_PROMPT = """Ты — qai-log-investigator, агент исследования логов.

Тебе дают вводные о баге. Твоя задача — найти в логах следы проблемы
и восстановить картину произошедшего.

Метод работы:
1. Начни с обзора: какие источники логов доступны.
2. Ищи по ключевым словам из вводных (id, суммы, названия операций),
   а также по уровням WARN и ERROR.
3. Найдя зацепку — читай контекст вокруг неё.
4. Стягивай события в таймлайн: что и когда произошло, что чему предшествовало.

Правила:
- Делай выводы ТОЛЬКО из строк лога, которые реально видел. Цитируй их.
- Если гипотеза не подтверждается логами — прямо скажи об этом.

Финальный ответ — отчёт:
## Таймлайн событий
## Ключевые улики (цитаты строк лога)
## Наблюдения и аномалии
## Что стоит проверить в коде"""

TASK_LIVE = """Расследуй BUG-1024 по логам стенда Online Boutique.

Суть: после уценки товара Sunglasses (product_id=OLJCESPC7Z, 19.99 -> 15.99) страница
товара показывает новую цену, а корзина считает по старой. Воспроизводится нестабильно,
«само проходит» примерно через час. Промокоды не применялись.

Сервисы-кандидаты: productcatalogservice, frontend, cartservice.
Ключевые слова: OLJCESPC7Z, cache, price, 19.99, 15.99."""

TASK_FIXTURES = """Расследуй BUG-1024 по логам за 2026-06-16 (app-2026-06-16.log).

Суть: после уценки товара SKU-4217 (12990 -> 10990) страница товара
показывает новую цену, а корзина списывает старую. Воспроизводится
нестабильно, «само проходит» примерно через час. Промокоды не применялись.

Ключевые слова: SKU-4217, 12990, 10990, cart total, price."""


def cluster_available() -> bool:
    try:
        proc = subprocess.run(
            ["kubectl", "--context", "kind-qai-boutique", "get", "deploy/productcatalogservice"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


if __name__ == "__main__":
    if "--fixtures" not in sys.argv and cluster_available():
        from skills.cluster_logs import CLUSTER_LOGS_TOOLS_IMPL as impl, CLUSTER_LOGS_TOOLS_SCHEMA as schema

        print("Источник: живые логи kind-qai-boutique (kubectl)")
        task = TASK_LIVE
    else:
        from tools import LOG_TOOLS_IMPL as impl, LOG_TOOLS_SCHEMA as schema

        print("Источник: файловые фикстуры fixtures/logs (кластер недоступен или --fixtures)")
        task = TASK_FIXTURES

    report = run_agent(
        name="qai-log-investigator",
        system_prompt=LOG_INVESTIGATOR_PROMPT,
        task=task,
        tools_schema=schema,
        tools_impl=impl,
    )
    print("\n" + "=" * 70)
    print(report)

# УПРАЖНЕНИЕ 1: уберите из промпта пункт «читай контекст вокруг неё» —
#   как изменится глубина расследования?
# УПРАЖНЕНИЕ 2: в skills/cluster_logs.py уменьшите MAX_LINES до 5 — посмотрите,
#   как агент адаптируется и уточняет паттерны поиска.
# УПРАЖНЕНИЕ 3: добавьте инструмент count_matches(deployment, pattern) —
#   агенту станет проще оценивать масштаб проблемы (сколько cache hit против miss).
