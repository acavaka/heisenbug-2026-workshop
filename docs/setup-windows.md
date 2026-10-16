# Подготовка Windows 11 x64 через WSL2

Для Windows на Intel/AMD подготовлен отдельный USB-каталог `Windows-x64-WSL2`.
Используйте его целиком: macOS arm64 бинарники, wheels и часть образов несовместимы.
Начните с `START-HERE.md`, затем `WINDOWS-SETUP.md` **в корне Windows-комплекта**.
Копия пошаговой инструкции в репозитории: [Windows offline](new-windows-offline.md).
Там находятся установщики Docker Desktop и WSL MSI, подготовленная Ubuntu 24.04 с Python 3.12,
Linux x64 wheels, Kind/kubectl/k8sgpt и 23 linux/amd64 образа.

Маршрут: импорт `QAIWorkshop` → Docker WSL integration → `setup.sh` → `source ~/qai-env.sh` →
проверка `python workshop/offline/check.py` → создание нового стенда через `workshop/offline/launch.py`.
Всё выполняется внутри WSL; проект лежит в `/home/qai/qai-workshop/qai-participant`.
Редактор либо открывает WSL-проект, либо запускает локальный MCP через `wsl.exe` (пример `MCP-WINDOWS.md` в комплекте).
Карточки заданий, правила доказательности и валидатор общие для всех платформ.

Проверка установки Python и MCP выполнена в изолированном Linux amd64 контейнере без сети.
Установка WSL/Docker, интеграция редактора и запуск Kind на настоящем Windows ещё требуют проверки.
Это не проверка Windows ARM. Подготовьте редактор и авторизацию модели заранее онлайн.
При отсутствии компонентов Windows/прав/виртуализации потребуется помощь IT или установка ОС-компонентов отдельно.

[Prework](participant-prework-draft.md) · [Чек-лист](meeting-windows-checklist.md) · [Задания](workshop-exercises-draft.md).
