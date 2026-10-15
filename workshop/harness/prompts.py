"""Единый источник промптов: workshop/prompts/<name>.md.

Формат файла: YAML-подобный frontmatter (name, description, tools, model) и тело.
Включения вида `{{rules-evidence}}` раскрываются из соответствующих prompts/*.md;
так подключаются общие правила доказательств, инфраструктуры и оркестрации.
Тот же файл рендерится в адаптеры Claude Code / Codex / Cursor (см. render.py),
поэтому промпт правится в одном месте.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass
class Prompt:
    name: str
    description: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "strong"
    max_steps: int | None = None
    body: str = ""


def load_prompt(name: str) -> Prompt:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    m = _FM.match(text)
    if m:
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        text = text[m.end():]
    includes = {p.stem: p for p in PROMPTS_DIR.glob("rules-*.md")}
    for key, path in includes.items():
        text = text.replace(f"{{{{{key}}}}}", path.read_text(encoding="utf-8").strip())
    return Prompt(
        name=meta.get("name", name),
        description=meta.get("description", ""),
        tools=[t.strip() for t in meta.get("tools", "").split(",") if t.strip()],
        model=meta.get("model", "strong"),
        max_steps=int(meta["max_steps"]) if meta.get("max_steps") else None,
        body=text.strip(),
    )


def list_roles() -> list[str]:
    return sorted(p.stem for p in PROMPTS_DIR.glob("qai-*.md"))
