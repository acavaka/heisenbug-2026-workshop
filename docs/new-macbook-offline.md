# Новый MacBook: установка QAI с флешки

Маршрут для **Apple Silicon (M1/M2/M3/M4/…)**, macOS 14 или новее, локального пользователя
с правом установки приложений. Для Intel этот комплект не подходит. Комфортный ориентир:
16 ГБ RAM и 30 ГБ свободного места. Флешка содержит установщики Docker Desktop 4.91.0
для arm64 и Python 3.12.6 universal2, Python wheels, kind/kubectl/k8sgpt и 23 образа стенда.

Установщики и артефакты подготовлены; подписи/хеши проверены. Новый Kind, все сервисы, HTTP-интерфейсы и live MCP проверены из USB
в отдельном кластере на ноутбуке ведущего с блокировкой внешних загрузок.
Docker на нём не переустанавливался; текущий стенд не перезапускался. Docker 4.91.0 в пакете отличается от установленного
у ведущего 4.42.1. Установка включённого Docker 4.91.0 и Docker VMM на чистом MacBook ещё не проверена.
В репетиции использован установленный Docker 4.42.1/Engine 28.2.2.

## 1. Скопировать комплект и проверить файлы

В Finder скопируйте **всю** папку USB-набора в домашнюю папку и назовите её `qai-usb`.
Внутри должны быть README.md, USB-SHA256SUMS.txt, installers, python-wheels, tools, images,
qai-participant.zip. Не запускайте команды из Downloads с другими
версиями установщиков. Можно отключить Wi-Fi на время настройки окружения.

Откройте встроенный Terminal (Spotlight → Terminal). Выполните:

```bash
uname -m
sw_vers -productVersion
cd "$HOME/qai-usb"
/usr/bin/shasum -a 256 -c USB-SHA256SUMS.txt
```

Ожидается arm64, macOS не ниже 14 и OK для каждого файла. Если контрольная сумма
не совпала — остановитесь и повторно скопируйте комплект. Проверка не требует Python.
Homebrew, Git, Xcode и Command Line Tools для этого маршрута не нужны.

## 2. Установить Python из PKG

В Finder откройте `qai-usb/installers/python-3.12.6-macos11.pkg`, пройдите штатный Installer.
Оставьте стандартные компоненты, в том числе pip; при необходимости введите пароль
своего локального пользователя. Сам pip устанавливается из встроенного ensurepip,
без загрузки с PyPI. Это установщик PSF, а не системный Python macOS.

**Не запускайте Install Certificates.command** из папки Python 3.12: он может скачать
certifi. certifi для нашего venv уже включён в локальный набор wheels.
Не выполняйте pip upgrade, brew install, xcode-select --install или установку Rosetta.

Проверка в Terminal (явный путь исключает запуск Apple python3 shim):

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 --version
```

Ожидается Python 3.12.6. Если путь отсутствует, установка PKG не завершена.

## 3. Установить Docker Desktop из DMG

Откройте `qai-usb/installers/Docker-4.91.0-apple-silicon.dmg`.
Перетащите Docker.app в Applications, дождитесь копирования, затем запустите Docker
из Applications. Примите условия использования самостоятельно. Для локального Engine
не требуется вход в Docker Hub; если доступен Skip, используйте его. Корпоративные
политики с обязательным входом нужно согласовать до занятия.

Настройки **только нового учебного ноутбука**:

- Отключите автоматическое скачивание обновлений, если оно включено.
- Оставьте встроенный Kubernetes Docker Desktop выключенным: используем Kind.
- Не включайте Docker Model Runner, MCP Toolkit, расширения и предлагаемые примеры.
- Для маршрута без Rosetta выберите Settings → General → Virtual Machine Manager →
  **Docker VMM**, затем Apply & restart. Это встроенный вариант Docker; он поддерживает
  amd64-эмуляцию без Rosetta, но медленнее и имеет статус Beta.
- В Resources выделите ориентировочно 4 CPU и 8 ГБ памяти, если ноутбук позволяет.

Не запускайте softwareupdate --install-rosetta: это скачивание. Если без Rosetta
эмуляция не проходит проверку ниже, не пытайтесь компенсировать её загрузками в зале:
сообщите ведущему и используйте файловый replay. Не изменяйте настройки рабочего Docker
с существующими проектами по этой инструкции.

В Terminal подготовьте переменные и PATH. Эти строки нужны в каждом новом терминале:

```bash
export QAI_USB="$HOME/qai-usb"
export QAI_PROJECT="$HOME/qai-workshop/qai-participant"
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$QAI_USB/tools:/Applications/Docker.app/Contents/Resources/bin:$HOME/.docker/bin:$PATH"
chmod +x "$QAI_USB/tools/kind" "$QAI_USB/tools/kubectl" "$QAI_USB/tools/k8sgpt"
docker --version
docker info
kind version
kubectl version --client
k8sgpt version
```

Ожидается работающий Docker Engine; kind v0.27.0, kubectl v1.31.1, k8sgpt v0.4.40.
Если CLI найден, но docker info не проходит, дождитесь запуска Engine и разберите
его ошибку. Не выполняйте docker login/pull/build или docker run hello-world.

## 4. Распаковать участника и установить зависимости

Не смешивайте рабочие каталоги участника и ведущего. Если qai-workshop уже существует,
выберите новый пустой каталог и соответственно измените QAI_PROJECT.

```bash
mkdir -p "$HOME/qai-workshop"
ditto -x -k "$QAI_USB/qai-participant.zip" "$HOME/qai-workshop"
cd "$QAI_PROJECT"
python3 workshop/offline/install.py --wheels "$QAI_USB/python-wheels"
workshop/.venv/bin/python workshop/offline/check.py
```

Установка использует только флешку (--no-index, --require-hashes), не перезаписывает
существующий venv и проверяет платформу. Ожидается PASS проверки старта: зависимости,
реестр, репорт, код order-worker, report/pods, оба MCP replay. Check задания trace_to_logs
до вашей реализации ожидаемо даёт FAIL — сводная проверка учитывает это.
API-ключ для этих действий не нужен. Не копируйте .env другого участника.

## 5. Загрузить образы и проверить эмуляцию

```bash
cd "$QAI_PROJECT"
mkdir -p microservices-demo/hack/offline/images
gzip -dc "$QAI_USB/images/workshop-images.tar.gz" > microservices-demo/hack/offline/images/usb.tar
docker load -i microservices-demo/hack/offline/images/usb.tar
```

Декомпрессия потребует примерно 4,5 ГБ дополнительно. Все образы загрузятся локально.
Не подменяйте теги другими версиями. Отдельно проверьте встроенную amd64-эмуляцию
коротким запуском Node из существующего образа paymentservice:

```bash
docker run --pull=never --rm --network=none --platform=linux/amd64 --entrypoint=node boutique/paymentservice:v0.10.0 --version
```

Ожидается версия Node и exit 0. Это отдельный одноразовый контейнер, сервис приложения
в нём не запускается. --pull=never исключает скачивание образа, --network=none отключает
сеть контейнера. Exec format error/аварийное завершение означает неработающую эмуляцию;
не переходите к запуску стенда. Тест одной программы не гарантирует работу всех сервисов.

```bash
workshop/.venv/bin/python workshop/offline/preflight_images.py --allow-amd64-emulation
```

Ожидается valid=true, images_checked=23; warnings об amd64 штатны для данного пакета.
Если есть missing/wrong platform — остановитесь. Флаг разрешает смешанную архитектуру,
а фактическая проверка эмуляции выполнена предыдущей командой.

## 6. Создать стенд на новом MacBook

Следующие команды создают учебный кластер **на этом ноутбуке**. Их не выполняли на
текущем стенде ведущего при сборке установщиков. В первом терминале:

```bash
cd "$QAI_PROJECT"
workshop/.venv/bin/python workshop/offline/launch.py --usb "$QAI_USB" --allow-amd64-emulation
export KUBECONFIG="$QAI_PROJECT/workshop/.local/kind.kubeconfig"
workshop/.venv/bin/python workshop/offline/verify_stand.py --context kind-qai-boutique --kubeconfig "$KUBECONFIG" --timeout 0
kubectl --context kind-qai-boutique get pods
```

launch.py откажется изменять уже существующий кластер или перезаписывать kubeconfig.
Если стенд подготовлен заранее, пропустите fresh launch и выполните verify_stand.py
с его kubeconfig. Для нового стенда используйте только launch.py: он проверяет хеши,
вызывает прежний up-offline и дополнительно требует Ready у всех 18 Deployment.
Сам up-offline может напечатать Done при непрошедшем ожидании, поэтому отдельно
его сообщение не является приёмкой. Манифесты используют Never; код и образы не собираются. До подготовки qai-training сервисы стенда
должны быть Ready; loadgenerator намеренно выключен. ImagePullBackOff/ErrImageNeverPull
— ошибка подготовки, не учебный баг; не лечите её docker pull.

Во втором Terminal повторите export из шага 3 и добавьте
`export KUBECONFIG="$QAI_PROJECT/workshop/.local/kind.kubeconfig"`, затем:

```bash
cd "$QAI_PROJECT/microservices-demo"
chmod +x hack/workshop/ports-workshop.sh
./hack/workshop/ports-workshop.sh
```

Оставьте Terminal открытым. В браузере: http://127.0.0.1:8080 (витрина),
http://127.0.0.1:3000 (Grafana), http://127.0.0.1:8233 (Temporal UI).
Для общей read-only проверки из первого Terminal можно выполнить:

```bash
cd "$QAI_PROJECT"
workshop/.venv/bin/python workshop/offline/check_http.py --context kind-qai-boutique --kubeconfig "$KUBECONFIG"
```

Он использует временные свободные localhost-порты и закрывает свои port-forward.
Это подходит и при занятых стандартных портах; проверка не создаёт заказы. **Не запускайте verify-stack.sh как read-only smoke:** он создаёт
заказы, учебные workflow и генерирует trace. Подготовка live-багов — отдельное действие ведущего.

## 7. Получить учебный read-only доступ

Ведущий заранее подготавливает отдельный qai-training и выдаёт личный read-only профиль
с локальным путём к mcp-live.json и kubeconfig. Профиль имеет срок действия; при истечении
запросите обновление у ведущего. Административный kubeconfig не копируйте и не публикуйте.
Настройка MCP выполняется по карточке задания 3. Подготовка неисправности не входит
в инструменты агента и команды участника; Boutique и order-worker не меняются.

## 8. Открыть материалы и подключить модель

Рабочий корень редактора — **только** `$QAI_PROJECT`. Откройте docs/workshop-kit.md.
Редактор/агент не входит в этот комплект: используйте заранее установленный привычный
Codex, Claude Code или Cursor с собственной авторизацией. Модель по подписке требует
интернет, поэтому включите сеть после offline-проверки окружения. Python API smoke не
запускайте ради проверки подписки. Без клиента модели доступны read-only инструменты,
ручное задание 1, данные и проверки остальных заданий, но полноценного LLM-расследования нет.

## Что считать успехом

Подписи и хеши установщиков проходят; Python/Engine доступны; offline/check.py — PASS;
эмуляция — exit 0; preflight — valid=true; core pods — Ready; UI открываются; read-only
профиль ограничен qai-training; редактор видит нужные MCP. Только после этих пунктов
отмечайте новый ноутбук готовым. Наличие всех файлов на USB не заменяет этой проверки.

Источники для ведущего: [Docker install](https://docs.docker.com/desktop/setup/install/mac-install/),
[Docker VMM](https://docs.docker.com/desktop/features/vmm/),
[Docker 4.91.0 checksums](https://desktop.docker.com/mac/main/arm64/239619/checksums.txt),
[Python 3.12.6](https://www.python.org/downloads/release/python-3126/).
Участнику не требуется открывать эти страницы для установки: файлы уже в комплекте.
