# Подключите инструменты для задания 4

`workshop/application_mcp.py` предоставляет редакторам тот же application-валидатор, что
Python-харнесс. Модель редактора сама расследует; Python здесь исполняет инструменты,
хранит первичные наблюдения и проверяет ответ. OpenAI API-ключ серверу не нужен.

## Когда это нужно

Подключите `qai_application` до практики. Он читает готовые файлы задания 4 и проверяет отчёт агента. Для задания 3 используется другой сервер — k8sgpt.

## Подключение

Сначала установите зависимости из `workshop/requirements.txt` в `workshop/.venv`.
Используйте абсолютные пути вашей машины. Пример Codex (`config.toml`):

```toml
[mcp_servers.qai_application]
command = "/ABS/REPO/workshop/.venv/bin/python"
args = ["/ABS/REPO/workshop/application_mcp.py", "--mode", "replay", "--case", "complete"]
required = true
```

Для Windows executable — `C:/ABS/REPO/workshop/.venv/Scripts/python.exe`.
В Cursor/Claude Code создайте stdio MCP с теми же command и args:

```json
{
  "mcpServers": {
    "qai_application": {
      "command": "/ABS/REPO/workshop/.venv/bin/python",
      "args": ["/ABS/REPO/workshop/application_mcp.py", "--mode", "replay", "--case", "complete"]
    }
  }
}
```

Замените `/ABS/REPO` на абсолютный путь к своей копии проекта. Добавляйте секцию сервера, сохраняя существующие подключения.

| Программа | Куда добавить |
|---|---|
| Codex | `.codex/config.toml` доверенного проекта либо пользовательский config.toml |
| Claude Code | `.mcp.json` в корне проекта, объект `mcpServers.qai_application` |
| Cursor | `.cursor/mcp.json`, объект `mcpServers.qai_application` |

Перезапустите MCP и убедитесь,
что видны пять инструментов `qai_*`. В интерактивном Codex подтвердите вызовы этого сервера.
Для заранее разрешённого неинтерактивного read-only прогона можно задать только этому серверу:
`default_tools_approval_mode = "approve"`. Без подтверждения `codex exec` может остановиться
на `MCP tool call requires approval, but approval policy is never`. Не отключайте общий sandbox.
[Параметры MCP Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

Сервер использует **вашу реализацию correlate** из `workshop/skills/trace_logs.py`. Доступны case: complete, missing-logs, incomplete-trace, no-ids, invalid-trace.
После изменения реализации или case перезапустите сервер и начните новое расследование.

## Как проверить подключение до практики

В новом чате попросите: «На сервере qai_application вызови qai_begin для BUG-LAB-01, затем qai_catalog с полученным investigation_id. Покажи доступные инструменты. Данные бага пока не собирай, расследование не начинай».

Ожидается успешный ответ сервера, список доступных инструментов и пустой каталог наблюдений. Если сервер не появился, проверьте абсолютные пути к Python и application_mcp.py, установленные зависимости и разрешение на вызовы MCP. При ошибке разрешений обратитесь к ведущему. Сам BUG-LAB-01 расследуем после реализации функции в задании 4.

## Задание агенту

> Расследуй BUG-LAB-01 через MCP qai_application. Это файловый replay, не живой стенд.
> Используй общие правила QAI. Создай investigation_id, собирай первичные данные через
> qai_observe; доступные схемы получай из qai_catalog. Отделяй факты от гипотез, исключай
> чужие записи только по наблюдаемым признакам, сохраняй неизвестное влияние пропусков.
> Проверь код только после подтверждения корреляции. Отправь обычный application-вердикт
> через qai_validate и сообщи его фактический результат. Ничего не исправляй в сервисах.

1. `qai_begin(bug_id)` создаёт отдельное расследование и возвращает схемы инструментов.
2. `qai_observe(investigation_id, tool, arguments)` исполняет реальный инструмент и сохраняет
   его ответ. Скопированный текст из чата/CLI не становится зарегистрированной уликой.
3. `qai_catalog` возвращает evidence и observed_file_lines. `qai_evidence_get` позволяет
   прочитать выбранный фрагмент или полный первичный ответ.
4. `qai_validate(investigation_id, draft)` раскрывает evidence_ref в source/quote и вызывает
   неизменённый `harness/verdict.py`. При отказе исправляйте ответ либо собирайте данные.

Draft: `bug_id`, `investigation_type="application"`, `root_cause`, `culprit_files`,
`confidence`, `reasons`, `evidence[{claim,kind,evidence_ref}]`, `false_leads`, `red_team`
(три ответа), `limitations`, `fix_direction`. Файлы — реальные `file:line` из каталога.
Для вывода/гипотезы без цитаты допустима пустая ссылка; для факта — только существующий ID.
Наблюдения принадлежат runtime: поле tool_observations в draft запрещено.

Успех — **ответ инструмента `valid=true`**, а не текст модели «проверено».
Валидатор проверяет контракт и происхождение цитат; смысл причинного вывода всё равно
проверяет человек и поведенческий eval. Принятый low — допустимый результат неполных данных.

## Роли и границы

Все роли используют один investigation_id одного MCP-процесса. Если редактор запускает
отдельный сервер каждому субагенту, выполняйте роли в основной сессии: ссылки между серверами
не переносятся. Не называйте последовательную работу по ролям запуском отдельных субагентов.
Infrastructure MCP k8sgpt остаётся отдельным сервером; выбирайте сервер явно, не смешивайте ID.

Replay читает только подготовленные файлы BUG-LAB-01. `--mode live` — отдельный явный режим
для read-only инструментов реестра QAI; требует настройки путей и адресов окружения.
Он не предоставляет runbook_append, postgres_query, shell или административные команды.
Сервер не загружает workshop/.env автоматически:
нужные не секретные переменные (например BOUTIQUE_ROOT, TEMPO_URL, KUBECTL_CONTEXT) передаются
через env конфигурации MCP. API-ключ модели редактора сюда не передавайте.

## Temporal в live-режиме

Внутри `qai_observe` доступны `temporal_list_workflows`, `temporal_inspect` и `temporal_history`.
Это общие реализации с Python-харнессом и CLI; внешних MCP-инструментов по-прежнему пять.
Синхронные инструменты исполняются вне event loop MCP, а наблюдения и проверка вердикта
обрабатываются последовательно. `temporal_inspect` может безопасно использовать свой asyncio-клиент.

Передайте `TEMPORAL_HOST` и `TEMPORAL_NAMESPACE` через env MCP, затем перезапустите сервер.
Поиск и история доступны только при `--mode live`; BUG-LAB-01 replay не обращается к Temporal.
[Настройка, пагинация, границы доказательств и проверки](temporal-tools.md).
