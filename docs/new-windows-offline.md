# Установка с флешки на Windows

## 1. Требования и проверка

Windows 11 x64 на Intel/AMD, включённая аппаратная виртуализация, права администратора для настройки ОС.
Проверьте совместимость актуального Docker Desktop с вашей сборкой Windows:
https://docs.docker.com/desktop/setup/install/windows-install/ . Корпоративная политика может запрещать WSL/Docker.
Не рассчитывайте на установку в практические 60 минут. Сделайте это заранее.

Скопируйте всю папку в `C:\qai-usb\windows`, откройте там PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-Pack.ps1
```

При ошибке хеша остановитесь и скопируйте комплект заново.

## 2. WSL2 без Microsoft Store

В PowerShell **от администратора** включите компонент из локального образа Windows:

```powershell
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart /LimitAccess
```

`/online` означает работающую Windows, а не скачивание. `/LimitAccess` запрещает обращение к Windows Update.
Если Windows сообщает об отсутствии исходных компонентов, нужен соответствующий установочный носитель Windows/помощь IT;
этот комплект не содержит дистрибутив самой Windows. Не продолжайте с неполной установкой компонента.

Откройте `installers\WSL-x64.msi`, установите WSL и перезагрузите ноутбук.
Проверка в обычном PowerShell: `wsl --version`. Не запускайте `wsl --install` без параметров — это загружает дистрибутив.

## 3. Импорт подготовленной Ubuntu

В обычном PowerShell из `C:\qai-usb\windows`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Import-WSL.ps1
wsl --list --verbose
```

Должна появиться `QAIWorkshop`, VERSION 2. Импорт не затрагивает другие дистрибутивы и отказывается
перезаписывать существующий `QAIWorkshop`. Пользователь внутри — `qai`, домашняя папка `/home/qai`.
Образ содержит Ubuntu 24.04, Python 3.12 и venv/pip. Отдельный Windows Python для этого маршрута не нужен.

## 4. Docker Desktop

Откройте `installers\Docker-Desktop-Installer.exe`, выберите WSL2 backend. После установки запустите Docker Desktop,
примите его условия. В Settings → General включите WSL2 engine; в Resources → WSL Integration включите **QAIWorkshop**,
нажмите Apply & Restart. Используйте Linux containers. Не включайте встроенный Kubernetes Docker Desktop: здесь Kind.
Установка Docker Desktop включает его собственные условия лицензирования.

Откройте WSL из PowerShell:

```powershell
wsl -d QAIWorkshop
```

Внутри WSL:

```bash
docker info
bash /mnt/c/qai-usb/windows/setup.sh
source ~/qai-env.sh
cd ~/qai-workshop/qai-participant
```

`setup.sh` проверяет хеши, распаковывает новый проект, устанавливает wheels с `--no-index --require-hashes`,
проверяет зависимости. Существующий проект/venv не перезаписывает. При частичной ошибке ничего не удаляйте вслепую:
сохраните свои изменения и обратитесь к ведущему. Python-пакеты из интернета не скачиваются.

## 5. Новый локальный стенд

В той же WSL-сессии, после `source ~/qai-env.sh`:

```bash
python workshop/offline/check.py
python workshop/offline/launch.py --usb /mnt/c/qai-usb/windows
```

Первая команда проверяет инструменты и replay/MCP без модели и без обращения к кластеру.
Вторая создаёт новый Kind и сервисы из локального архива; она откажется менять существующий кластер или kubeconfig.
Не используйте `--allow-amd64-emulation`: здесь все образы x64.

В отдельном WSL-терминале оставьте работающими port-forward:

```bash
source ~/qai-env.sh
cd ~/qai-workshop/qai-participant
bash microservices-demo/hack/workshop/ports-workshop.sh
```

Откройте адреса из вывода скрипта в браузере Windows. Если localhost не пробрасывается, проверьте WSL networking,
VPN и firewall с IT; не отключайте firewall целиком. Учебный namespace и read-only kubeconfig ведущий готовит отдельно
по `docs/k8sgpt-mcp.md`. Само подключение live MCP — задание 3. Встроенный административный kubeconfig агенту не выдавайте.

## 6. Редакторы и MCP

Все Python-команды из карточек выполняйте **в WSL**, с активным `source ~/qai-env.sh`.
Открывайте проект в WSL-режиме редактора, если он поддерживается; расширение WSL/сервер редактора установите заранее онлайн.
Для Windows-редактора MCP можно запустить через `wsl.exe`: пример — [MCP-WINDOWS.md](mcp-windows.md).
Не используйте Windows `C:\...` пути как Linux-пути внутри WSL.

Для Python-харнесса заполните `workshop/.env` своим API-провайдером по `docs/multi-provider.md`.
Для Codex/Cursor/Claude Code по подписке API-ключ в этом файле не нужен: модель работает в редакторе, локальный MCP даёт инструменты.
Секреты не копируйте обратно на общую флешку.

## 7. Что открыть на занятии

`docs/workshop-kit.md` → четыре карточки заданий. Все участники работают по одной программе.
Ожидаемый FAIL у начальной заготовки `trace_to_logs` — часть задания, не ошибка установки.

Источники: [WSL offline install](https://learn.microsoft.com/en-us/windows/wsl/install#offline-install),
[импорт дистрибутива](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro),
[Docker WSL2](https://docs.docker.com/desktop/features/wsl/).
