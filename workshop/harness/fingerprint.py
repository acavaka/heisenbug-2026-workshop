"""Группировка похожих сообщений падений по fingerprint БЕЗ LLM (паттерн из систем диагностики E2E-падений).

Зачем: если упало N тестов/репортов, дорогую LLM-диагностику запускаем
по одному представителю каждой группы, остальные получают ссылку на его отчёт.

Нормализация: убираем UUID, hex-хэши, IP, timestamp, числа. Что остаётся,
и есть сигнатура (сервис + текст ошибки). Совпадение сигнатур не доказывает общую причину.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

_NOISE = [
    (re.compile(r"(\w+)=\S+"), r"\1=<v>"),  # order=ORD-1 request_id=7f3a → ключ остаётся, значение нет
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "<uuid>"),
    (re.compile(r"\b[0-9a-f]{16,64}\b", re.I), "<hex>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?Z?"), "<ts>"),
    (re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b"), "<ip>"),
    (re.compile(r"\b(ORD|TO|BUG|INC)-[\w-]+\b"), "<id>"),
    (re.compile(r"\d+"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def normalize(text: str) -> str:
    text = text.lower()
    for rx, repl in _NOISE:
        text = rx.sub(repl, text)
    return text.strip()


def fingerprint(component: str, message: str) -> str:
    sig = f"{component.lower()}|{normalize(message)}"
    return hashlib.sha1(sig.encode()).hexdigest()[:10]


def group_failures(failures: list[dict]) -> dict[str, list[dict]]:
    """failures: [{"id": ..., "component": ..., "message": ...}] → {fingerprint: [failures]}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for f in failures:
        groups[fingerprint(f.get("component", ""), f.get("message", ""))].append(f)
    return dict(groups)


if __name__ == "__main__":
    demo = [
        {"id": "TO-4412", "component": "payment", "message": "charge timeout order=ORD-a3f81c02 request_id=7f3a... attempt=1"},
        {"id": "TO-4413", "component": "payment", "message": "charge timeout order=ORD-b91e77aa request_id=12cd... attempt=1"},
        {"id": "TO-4408", "component": "order-worker", "message": "ship failed: shipping carrier unavailable, retry 51"},
    ]
    groups = group_failures(demo)
    assert len(groups) == 2, groups
    for fp, members in groups.items():
        print(fp, [m["id"] for m in members])
    print("fingerprint OK")
