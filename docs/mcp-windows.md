# MCP через WSL из Windows-редактора

Сначала выполните `setup.sh`. В конфигурации MCP Windows-редактора укажите stdio-сервер:

```json
{
  "mcpServers": {
    "qai-application": {
      "command": "wsl.exe",
      "args": ["--distribution", "QAIWorkshop", "--exec", "/home/qai/.local/bin/qai-application-mcp", "--mode", "replay", "--case", "complete"]
    }
  }
}
```

Для Codex (`config.toml`) тот же запуск:

```toml
[mcp_servers.qai_application]
command = "wsl.exe"
args = ["--distribution", "QAIWorkshop", "--exec", "/home/qai/.local/bin/qai-application-mcp", "--mode", "replay", "--case", "complete"]
```

Для `no-ids` замените последнее значение и перезапустите MCP. Не переносите evidence refs между сессиями.
Должны появиться qai_begin, qai_observe, qai_catalog, qai_evidence_get, qai_validate.
Правила принятия вердикта общие: фактический valid=true; SKILL.md не заменяет валидатор.

В WSL-редакторе вместо wsl.exe используйте напрямую `/home/qai/.local/bin/qai-application-mcp` и аргументы
`--mode replay --case complete`. Путь проекта во всех инструментах — Linux-путь.

Live k8sgpt: настройте read-only kubeconfig внутри WSL по `docs/k8sgpt-mcp.md` проекта.
Для его MCP применяйте тот же транспорт `wsl.exe --distribution QAIWorkshop --exec ...` к Linux-команде
из инструкции. Windows kubeconfig/пути автоматически в Linux не преобразуются.
API-ключ модели для локального MCP не нужен. Авторизация модели остаётся в редакторе.

## Задание 3: k8sgpt

Сначала получите личный read-only kubeconfig и сохраните **в WSL** как `/home/qai/qai-training-readonly.kubeconfig`.
Выполните `chmod 600 ~/qai-training-readonly.kubeconfig`. Это не административный kubeconfig Kind.
Добавьте сервер с именем `k8sgpt` в привычный редактор (существующие секции сохраните):

```json
{
  "mcpServers": {
    "k8sgpt": {
      "command": "wsl.exe",
      "args": ["--distribution", "QAIWorkshop", "--exec", "/home/qai/.local/bin/qai-k8sgpt-mcp", "--config", "/home/qai/qai-workshop/qai-participant/workshop/mcp/live.example.json"]
    }
  }
}
```

Codex TOML: секция `[mcp_servers.k8sgpt]`, `command = "wsl.exe"`, `args` — тот же массив.
Для replay замените `live.example.json` на `replay.json`; read-only kubeconfig тогда не нужен.
Для WSL-редактора команда — `/home/qai/.local/bin/qai-k8sgpt-mcp`, аргументы начинаются с `--config`.
Инструменты вызывайте по правилам карточки: `qai_begin` → `qai_observe` → `qai_validate`, а не только raw analyze.
