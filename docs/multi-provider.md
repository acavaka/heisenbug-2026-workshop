# Один агент, четыре канала

Принцип: **скилл = детерминированный скрипт + описание, промпт роли = один файл**.
LLM-хост (OpenAI SDK, Claude Code, Codex, Cursor) только рассуждает и вызывает скиллы.

```
workshop/prompts/*.md     ← единственный источник промптов ролей (frontmatter: tools, model)
workshop/skills/*.py      ← скиллы (функция + JSON-схема)
workshop/qai_tool.py      ← CLI к любому скиллу: python workshop/qai_tool.py <tool> key=value
AGENTS.md                 ← правила для всех хостов
workshop/render.py        ← генерирует адаптеры ниже
  .claude/agents/qai-*.md, .claude/skills/qai/SKILL.md     Claude Code
  .agents/skills/qai/SKILL.md                              Codex CLI, Cursor
  .cursor/rules/qai.mdc, CLAUDE.md                         Cursor, Claude Code
```

После правки промпта: `python workshop/render.py` (проверка в CI: `python workshop/render.py --check`).

## Матрица

| Канал | Как | Команда |
|---|---|---|
| OpenAI | DIY-харнесс, `OPENAI_API_KEY` | `python workshop/e2e.py --read-only BUG-1024` |
| Другой OpenAI-совместимый провайдер (прокси, OpenRouter, Ollama) | `OPENAI_BASE_URL` + `MODEL` в `.env`, тот же харнесс | тот же `e2e.py` |
| Claude Code | субагенты `.claude/agents/qai-*`, skill `/qai` | `claude` → `/qai BUG-TEMP-01` |
| Claude Code headless (CI) | `claude -p` | см. ниже |
| Codex CLI | `AGENTS.md` + `.agents/skills/qai` | `codex exec "/qai BUG-1024"` |
| Cursor | `.cursor/rules/qai.mdc` + `.agents/skills` | в чате `/qai BUG-1024` |
| k8sgpt MCP | общая интеграция во всех хостах, explain=false | [k8sgpt-mcp.md](k8sgpt-mcp.md) |

## Headless-запуск Claude Code 

```bash
claude -p "/qai BUG-TEMP-02" \
  --append-system-prompt "Работай автономно: не задавай вопросов, при отсутствии данных фиксируй это в limitations." \
  --output-format stream-json --verbose \
  --allowedTools "Bash(python workshop/qai_tool.py --read-only *),Agent,mcp__k8sgpt__*,mcp__qai_application__*"
```

`stream-json` требует `--verbose`. Итоговый вердикт (JSON) забирайте из последнего сообщения.

## Что общего, что разное

| | DIY-харнесс | Claude Code | Codex / Cursor |
|---|---|---|---|
| Оркестратор | модель выбирает роли и досбор через `agents/orchestrator.py`; фиксированный `agents/qai.py` — только `--mode workflow` | основная сессия через skill `/qai` + `Agent` для 3 ролей | skill `/qai`: модель выбирает роли; при отсутствии общих MCP-сессий у субагентов выполняет роли в основной сессии |
| Изоляция контекста ролей | да (отдельные вызовы) | да (субагенты) | нет, если хост без субагентов |
| Ограничения роли | исполняемый реестр tools | Bash не является изоляцией команд; MCP ограничен gateway | правила роли текстом; MCP ограничен gateway |
| Модель на роль | `MODEL_FAST` / `MODEL_STRONG` | настройка хоста (генератор model не выставляет) | настройка хоста |

Вывод для участника: архитектура переносится, гарантии зависят от хоста. Где хост не даёт субагентов,
изоляцию и least privilege приходится держать дисциплиной промпта.

## MCP k8sgpt

Общий путь подключения и точные ограничения: [k8sgpt-mcp.md](k8sgpt-mcp.md).
Python выставляет обнаруженные MCP tools только investigator. В Claude Code MCP-сервер
называется k8sgpt и разрешён этому субагенту; в Codex/Cursor разделение ролей остаётся инструкцией.
Python проверяет происхождение фактов и вердикт в runtime. В редакторах тот же код
доступен через MCP: `qai_begin` → наблюдения через `qai_observe` → `qai_validate`.
Инфраструктура использует gateway k8sgpt; application — отдельный
[application MCP](application-mcp.md). Нужен фактический `valid=true`, самооценки
`confidence=high` недостаточно. Каталоги и investigation_id между серверами не смешиваются.
Для BUG-LAB-01 сервер работает на файловом replay; API-ключ ему не нужен.
