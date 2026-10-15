# k8sgpt через MCP: Python, Claude Code, Codex, Cursor

Общее задание: участник подключает сервер, видит его инструменты, агент делает настоящий
MCP-вызов и использует результат в расследовании. Выбор программы не меняет критерий сдачи.
Для live подготовлен отдельный namespace `qai-training`, read-only RBAC и неисправный
учебный сервис. Read-only профиль выдаёт ведущий; Boutique и order-worker не затрагиваем.

## Два режима

| Режим | Источник | Что подтверждает |
|---|---|---|
| `replay` | Локальный синтетический MCP-сервер | Discovery, вызовы, ограничения, ошибки, контракт вердикта |
| `live` | k8sgpt `serve --mcp` → Kubernetes | Реальные наблюдения после подготовки отдельного учебного окружения |

Replay использует настоящий stdio MCP, но не исполняет k8sgpt и не обращается к Kubernetes.
Нет автоматического переключения live → replay или MCP → CLI. В Python при ошибке подключения
investigator получает диагностическое наблюдение и остаётся без инструментов стенда.

## Подготовка и локальная проверка

Из корня репозитория, в окружении из [prework](participant-prework-draft.md) (USB macOS arm64: Python 3.12):

```bash
source workshop/.venv/bin/activate
python workshop/mcp_check.py --config workshop/mcp/replay.json --probe-replay
```

На Windows активируйте `workshop\.venv\Scripts\Activate.ps1` в PowerShell.
MCP SDK закреплён на `1.30.0`. Probe не требует API-ключа или kubeconfig.
Ожидается mode=replay, сервер `qai-synthetic-replay`, пять инструментов и два успешных ответа
get-resource/list-events. Ошибка подключения или вызова даёт ненулевой exit code.

## Python-харнесс

Добавьте в локальный `workshop/.env` абсолютный путь (без кавычек-плейсхолдеров):

```dotenv
QAI_MCP_CONFIG=/absolute/path/heisenbug_2026/workshop/mcp/replay.json
```

Путь для своей машины можно получить командой:

```bash
python workshop/mcp_config.py --host python --profile replay
```

Затем с настроенным провайдером LLM:

```bash
python workshop/e2e.py --read-only BUG-INFRA-01
```

Этот запуск вызывает LLM вашего харнесса. В отличие от `mcp_check`, ему нужен рабочий провайдер.
В replay investigator получает только MCP и локальные справочники, без kubectl/Tempo/SQL.
Инфраструктурный checker проверяет переданные улики без инструментов кода.
В JSON отчёта `tool_observations` должны быть реальные вызовы `mcp_k8sgpt_get_resource` и
`mcp_k8sgpt_list_events`, mode=replay, status=ok и effective args с namespace.
LLM не заполняет эти наблюдения: их записывает runtime. Replay не использовать для live-багов
BUG-1024/BUG-TEMP-*: это отдельный учебный набор данных.

## Редакторы и CLI-хосты

Сгенерируйте фрагмент для своей программы из активированного venv:

```bash
python workshop/mcp_config.py --host claude --profile replay
python workshop/mcp_config.py --host codex --profile replay
python workshop/mcp_config.py --host cursor --profile replay
```

Команда только печатает настройки с абсолютными путями и текущим Python; ничего не записывает.
Добавьте **только новую секцию k8sgpt**, сохранив существующие MCP-подключения:

| Хост | Куда добавить |
|---|---|
| Claude Code | project `.mcp.json`, объект `mcpServers.k8sgpt`; разрешить project server при запросе клиента |
| Codex | project `.codex/config.toml`, секция `[mcp_servers.k8sgpt]` в доверенном проекте, либо пользовательский config |
| Cursor | project `.cursor/mcp.json`, объект `mcpServers.k8sgpt`; текущий GitHub server сохранить |

Не коммитьте машинные абсолютные пути и секреты. После подключения обновите список MCP в хосте
или перезапустите сессию. Сервер должен называться `k8sgpt`, чтобы соответствовать разрешению
investigator `mcp__k8sgpt__*` в адаптере Claude Code. Сгенерированные файлы ролей обновляются
через `python workshop/render.py`, исходники промптов находятся в `workshop/prompts/`.

Для проверки попросите: «Через MCP k8sgpt прочитай Pod checkout-probe в namespace qai-training,
затем его события. Это replay, используй только этот источник». Проверьте фактические вызовы
в истории инструментов. Затем `/qai BUG-INFRA-01`. Список подключённых серверов сам по себе
не доказывает, что агент воспользовался интеграцией.

Gateway — MCP-клиент и MCP-сервер. Он передаёт разрешённые вызовы upstream по MCP и не заменяет
их shell-командой `k8sgpt analyze`. Python использует тот же клиент и ту же политику напрямую.
Для infrastructure gateway регистрирует реальные наблюдения через qai_observe и проверяет
вердикт через qai_validate тем же кодом, что Python. Полный поток и контракт:
[Доказательства по ссылкам](evidence-contract.md). Для application автоматическая проверка
в редакторах пока не подключена. Тесты MCP-протокола не заменяют репетицию UI каждой программы.

## Live-подключение — после подготовки учебного namespace

Целевая upstream-версия k8sgpt: `v0.4.40`. Бинарник следует установить заранее из
[официального release](https://github.com/k8sgpt-ai/k8sgpt/releases/tag/v0.4.40) под ОС/архитектуру
ноутбука и проверить версию. Установка актуального пакета без фиксации версии для зала нежелательна.
Настоящий бинарник и MCP-вызовы проверены на macOS arm64 с учебным Kind; другие ОС требуют репетиции.

`workshop/mcp/live.example.json` запускает `k8sgpt --config .../no-explain.yaml serve --mcp`.
Для ручной настройки нужен `QAI_KUBECONFIG` — абсолютный путь к **отдельному** kubeconfig с выбранным контекстом и
read-only RBAC учебного namespace. Его выдаёт ведущий после подготовки стенда. Общий admin
kubeconfig не нужен. Переменная `KUBECTL_CONTEXT` legacy-скиллов MCP-клиентом не используется.
GUI-хост должен получить QAI_KUBECONFIG через своё окружение или локальный env-блок подключения;
значение из workshop/.env native-клиенты автоматически не читают.

Когда окружение готово, переключите профиль в генераторе на `--profile live`, а в Python
QAI_MCP_CONFIG — на абсолютный путь к live.example.json. `mcp_check.py --config ...` без probe
делает initialize/tools/list; это ещё не подтверждение доступа к данным кластера.
`--probe-replay` отказывается работать при mode=live.

Политика gateway/харнесса:

- Пять upstream-инструментов (и пять локальных QAI-операций каталога/проверки): analyze, list-resources, get-resource, list-events, get-logs.
- Namespace обязателен и равен значению конфигурации; Secrets и cluster-wide ресурсы не выставляются.
- Для analyze только Pod/Deployment/Service, explain=false, без backend override.
- Config и изменение фильтров не выставляются. Прямой доступ к upstream из другого клиента
  не получает эти ограничения: нижняя граница прав — Kubernetes RBAC.
- Одна сессия на investigator, таймаут, закрытие процесса при выходе; ошибки MCP сохраняются как ошибки.
- Python сохраняет MCP-текст целиком до 200000 символов. Более крупный результат отклоняется
  с просьбой сузить запрос; JSON не обрезается посередине.

`no-explain.yaml` содержит синтетический нерабочий provider, необходимый для инициализации
upstream serve. Диагностика выполняется без explain; реальные ключи LLM k8sgpt здесь не нужны.
Не включайте explain и не заменяйте этот файл общей конфигурацией с ключами на занятии.

## Контракт инфраструктурного вердикта

`investigation_type=application` по умолчанию для старых отчётов: high требует код + улики стенда.
`investigation_type=infrastructure`: `culprit_files=[]` допустим; `culprit_resources` содержит
`kind`, `namespace`, `name`, `uid` каждого предполагаемого виновника.
Это полный отчёт runtime. Модель передаёт culprit_resource_refs и evidence_refs из каталога,
не собирает цитаты вручную; см. [контракт ссылок](evidence-contract.md).

Для high по каждому ресурсу нужны два факта с `resource` (та же четвёрка полей):

1. `source=mcp_k8sgpt_get_resource`, `evidence_role=configuration`, цитата из `spec` объекта.
2. `source=mcp_k8sgpt_list_events`, `evidence_role=symptom`, цитата reason/message/type из
   Warning event с совпадающим `involvedObject`, включая UID.

Все общие поля вердикта остаются обязательными. Medium требует хотя бы одну такую улику,
low допускает пустые ресурсы и диагноз с объяснением пробелов. Этот первый контракт сознательно
ограничен spec + Warning events: при отсутствии событий нельзя компенсировать их выдумкой.
Отсутствие событий не доказывает исправность, поскольку они могут истечь.

Проверка доказывает совпадение цитат и идентичность объекта, **не причинность или актуальность**
события. Агент и участник проверяют время, механизм отказа, альтернативы. Ответ analyze —
направление поиска; здоровые поды не исключают бизнес-баг. Такой баг расследуется по application.
Infrastructure learning в старый runbook-map отключён: его схема ожидает ссылку на исходник.

Контракт описан в [правилах доказательств](evidence-contract.md). Публичные проверки MCP-транспорта:
`tests/workshop/test_mcp_client.py`. Проверки с готовыми диагнозами хранятся у ведущего.

## Критерий задания, 15 минут

0–5: добавить конфигурацию и увидеть инструменты. 5–10: агент вызывает MCP и собирает объект/событие.
10–15: предъявить связь UID, цитаты, вердикт и ограничения. Установка зависимостей выполняется
заранее. Быстрым участникам: healthy replay и приложение с бизнес-ошибкой; они должны объяснить,
почему зелёный Kubernetes не снимает гипотезы ошибки приложения.

## Источники совместимости

Проверены схемы инструментов [k8sgpt v0.4.40](https://github.com/k8sgpt-ai/k8sgpt/blob/v0.4.40/pkg/server/mcp.go)
и [MCP Python SDK v1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
Форматы конфигураций: [Claude Code MCP](https://code.claude.com/docs/en/mcp),
[Codex MCP](https://developers.openai.com/codex/mcp), [Cursor MCP](https://cursor.com/docs/mcp).
Перед конференцией повторить smoke на фактических версиях хостов и ОС участников.

## Подготовленный live-профиль

Получите у ведущего read-only профиль для своего ноутбука: `workshop/.local/mcp-live.json`.
Он содержит абсолютные пути к установленному бинарнику и kubeconfig; чужие пути не копируйте.
Профиль ограничен namespace `qai-training`, операции записи запрещены. В нём exclusive=true:
Python investigator не получает инструменты других сервисов. Для native-клиентов замените путь
--config из mcp_config.py на этот файл. При истёкшем токене обратитесь к ведущему за обновлением.
