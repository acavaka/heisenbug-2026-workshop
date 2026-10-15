# Temporal: read-only поиск и история

Инструменты investigator общие для Python-харнесса, CLI и application MCP в Codex,
Cursor и Claude Code. Реализация: `workshop/skills/temporal_inspect.py`.
Модель/API-ключ для работы инструментов не нужен. Зависимость temporalio уже входит в requirements.

## Настройка

CLI читает `workshop/.env`; application MCP автоматически его не загружает.
Для MCP передайте окружение сервера и выберите `--mode live`:

```toml
[mcp_servers.qai_application]
command = "/ABS/REPO/workshop/.venv/bin/python"
args = ["/ABS/REPO/workshop/application_mcp.py", "--mode", "live"]
required = true

[mcp_servers.qai_application.env]
TEMPORAL_HOST = "127.0.0.1:7233"
TEMPORAL_NAMESPACE = "default"
```

В JSON-конфигурации Cursor/Claude Code это те же command/args и
`"env": {"TEMPORAL_HOST":"127.0.0.1:7233", "TEMPORAL_NAMESPACE":"default"}`.
Остальные параметры стенда и путей оставьте из своего профиля application MCP.
Temporal namespace не равен Kubernetes namespace и не выбирается аргументом модели.
После изменения env перезапустите MCP и начните новое расследование.

## Маршрут расследования

1. Если ID неизвестен, `temporal_list_workflows` читает одну страницу visibility.
   Используйте известные из репорта/источников тип workflow, статус или время в query.
   Query — синтаксис фильтра Temporal Visibility, не SQL к БД и не workflow query.
2. Кандидатов сопоставьте с инцидентом. Имя типа и статус сами по себе не устанавливают корреляцию.
3. `temporal_inspect(workflow_id, run_id)` читает описание конкретного исполнения.
   Старый вызов без run_id сохранён: он читает latest и возвращает фактический run_id.
4. `temporal_history(workflow_id, run_id)` требует оба ID. Сохраняйте eventId, eventType,
   eventTime и ссылки между событиями, например scheduledEventId/startedEventId.
5. При has_more=true передайте next_page_token в page_token следующего вызова с теми же
   query либо workflow_id/run_id. Токен связан также с namespace; для нового поиска он не подходит.
   continued=true помечает ответ, начинающийся не с первой страницы.
6. Если сбор остановлен раньше конца, явно укажите это. has_more=false означает только конец
   текущей последовательности страниц; Running workflow может получить новые события позднее.

В редакторе выполняйте весь маршрут через `qai_observe` одного application MCP и investigation_id.
Например: tool=`temporal_list_workflows`, arguments=`{"query":"ExecutionStatus = 'Running'","page_size":20}`.
После этого передавайте ID из настоящего ответа, а не из примера или догадки.
Ответы автоматически входят в каталог; используйте evidence_ref при qai_validate.
В Python роль investigator получает эти же функции через общий реестр и runtime.

Команды для ручной диагностики (CLI-вывод сам по себе не входит в MCP-каталог):

```bash
python workshop/qai_tool.py --read-only temporal_list_workflows "query=ExecutionStatus = 'Running'" page_size=20
python workshop/qai_tool.py --read-only temporal_inspect 'workflow_id=<ID из ответа>' 'run_id=<UUID из ответа>'
python workshop/qai_tool.py --read-only temporal_history 'workflow_id=<ID из ответа>' 'run_id=<UUID из ответа>' page_size=20
```

## Ограничения доказательств и доступа

- Visibility может отставать; пустая выборка не доказывает отсутствия workflow.
- История может агрегировать retry-попытки activity. Не обещайте получить каждую попытку
  или доказать бесконечный retry только по отсутствию завершающего события.
- ActivityCompleted не является независимым подтверждением внешнего платежа/возврата.
  Для этого нужен разрешённый источник внешнего эффекта и корреляция по ID.
- Полные protobuf-события возвращаются как JSON, в том числе payload в protobuf JSON-форме;
  инструмент не угадывает бизнес-смысл закодированных данных.
- Один вызов — одна страница, page_size от 1 до 100 (по умолчанию 20). Сервер может вернуть
  более крупный batch; общий ответ ограничен 120000 байт UTF-8. При превышении — TOOL ERROR,
  без обрезанного JSON и без успешной регистрации страницы. Уменьшите page_size/сузьте поиск;
  если единичное событие слишком велико, зафиксируйте limitation.
- Общий таймаут 20 секунд, RPC — 10 секунд. История не ждёт новых событий (wait_new_event=false).
- Ошибки SDK/сети/параметров не попадают в evidence как успешные факты.
- Tools используют только list/describe/history. Они не запускают, не сигналят, не отменяют,
  не завершают и не сбрасывают workflow, не выполняют код workflow query и не открывают SQL.
  Это ограничение доступных операций, а не настройка прав самой учётной записи Temporal.
- Валидатор сохраняет требования: high требует наблюдавшиеся факты кода и стенда, реальные
  culprit_files и корректные цитаты. Новые tools лишь зарегистрированы как источники стенда.

## Если подключение не работает

Ошибка MCP — ограничение источника, не повод обходить его через shell/другой сервер.
Разрешён один повтор; затем зафиксируйте ошибку и следующий шаг.

Running/Ready Pod, доступный Temporal UI и открывшийся TCP-туннель не гарантируют работу
локального gRPC. При `Connection refused`/`BrokenPipe` в port-forward ведущий проверяет
адрес listener Temporal: bind только на IP Pod может быть недоступен через loopback,
используемый port-forward. Изменение bind/деплой — отдельная административная задача;
агент расследования этого не делает.

В манифесте `microservices-demo/hack/workshop/temporal.yaml` задан `BIND_ON_IP=0.0.0.0`,
чтобы gRPC был доступен и по IP Pod, и через port-forward. После административного
обновления Deployment ведущий дожидается rollout и заново поднимает локальный туннель.
Проверяйте фактическим `temporal_list_workflows`, а не только открытым TCP-портом.
Успешный пустой список подтверждает доступ к API, но не наличие данных учебного инцидента.
Перед live-практикой ведущий проверяет retention и наличие свежих workflow/run ID.
Подготовка учебных операций выполняется отдельно: агент расследования не создаёт заказы
и не вызывает endpoints воспроизведения ради получения доказательств.

## Проверки без модели и стенда

```bash
python -m unittest discover -s tests/workshop -p 'test_temporal*.py' -v
python workshop/render.py --check
```

Тесты проверяют пределы, пагинацию, точный run_id, ошибки, общий каталог и отклонение
неподтверждённого high. Stdio-тест использует настоящий application MCP с **синтетическим
Temporal-клиентом**: это проверка протокола и интеграции, не доказательство доступности живого Temporal.
Тестовые данные не содержат ответов на учебные баги.
