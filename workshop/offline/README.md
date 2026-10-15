# QAI offline: подготовка без загрузки зависимостей

Проверенный Python-маршрут: macOS arm64, Python 3.12.6. В USB добавлены установщики
Docker Desktop 4.91.0 arm64 и Python 3.12.6 universal2. Для нового ноутбука начните с
[пошаговой инструкции](../../docs/new-macbook-offline.md); затем вернитесь к проверкам ниже.
Свежий Kind из USB на установленном Docker 4.42.1 проверен; установка Docker 4.91.0
и Docker VMM на чистом MacBook ещё не проверены.
Участнику выдаётся публичный USB-каталог с qai-participant.zip, `python-wheels`,
`tools` (kind/kubectl/k8sgpt), `images` и `installers`. Архив ведущего хранится отдельно.

## Участнику

Из корня распакованного qai-participant:

```bash
python3 workshop/offline/install.py --wheels /Volumes/USB/qai/python-wheels
workshop/.venv/bin/python workshop/offline/check.py
```

Путь USB замените своим. Для путей с пробелами используйте кавычки. install.py создаёт
новый workshop/.venv, проверяет SHA-256, использует --no-index/--require-hashes и не
обращается к PyPI. Существующий venv не перезаписывает. check.py не запускает модель,
не требует API-ключа и не читает live-кластер. TODO trace_to_logs ожидаемо не проходит.

Бинарники tools предназначены только для darwin/arm64. Добавьте каталог в PATH:

```bash
export PATH="/Volumes/USB/qai/tools:$PATH"
kind version
kubectl version --client
k8sgpt version
```

Не вызывайте install_k8sgpt.py: он скачивает бинарник. Ведущий подготавливает namespace
и read-only профиль отдельно; профиль не включается в общий USB и имеет срок действия.

## Образы стенда

Образы сервисов находятся в Docker-архиве, а не внутри образа Python-агента.
Код Boutique/order-worker включён в ZIP для чтения; контейнерные образы — отдельный файл.
Новый образ QAI для текущего локального маршрута не требуется.

После получения **полного** набора образов от ведущего:

```bash
mkdir -p microservices-demo/hack/offline/images
gzip -dc /Volumes/USB/qai/images/workshop-images.tar.gz > microservices-demo/hack/offline/images/usb.tar
docker load -i microservices-demo/hack/offline/images/usb.tar
workshop/.venv/bin/python workshop/offline/preflight_images.py
```

Если полный набор содержит amd64 сервисы при arm64 узле, нужна проверенная Docker-эмуляция.
Только после её проверки ведущим допустим явный --allow-amd64-emulation. Флаг не проверяет
работоспособность эмуляции. При missing image запуск останавливается; скачивания fallback нет.
После успешного preflight используйте workshop/offline/launch.py --usb /PATH/TO/USB
--allow-amd64-emulation из корня нового проекта. Он вызывает прежний up-offline.sh,
защищает существующие кластеры/kubeconfig и дополнительно проверяет 18 Deployment.
Этот маршрут создаёт новый локальный стенд; проверен в отдельном Kind без внешних загрузок.
Архив загрузки один; load-images.sh найдёт его в images/*.tar и загрузит нужные теги в Kind.

**Состояние подготовленного набора:** 23 образа; stock Boutique linux/amd64, Kind и
workshop builds linux/arm64. Шаблон подготовки qai-training использует уже экспортируемый
boutique/busybox:latest с imagePullPolicy: Never. Отсутствующий ConfigMap по-прежнему
создаёт учебную неисправность. Текущий стенд с прежним busybox:1.36.1 не изменялся;
новый шаблон нужно применить при отдельной разрешённой подготовке ноутбуков.
Манифест образов фиксирует ID содержимого каждого тега. Для Apple Silicon нужен
проверенный маршрут эмуляции stock-сервисов; данный экспорт не является новым live-прогоном.

## Ведущему

```bash
workshop/.venv/bin/python workshop/offline/prepare_local_wheels.py --output /NEW/PATH/python-wheels
python3 workshop/offline/export_images.py --output /NEW/PATH/images
```

Обе команды работают с локальными ресурсами. Экспорт не делает pull/build и не меняет
кластер; при недостающем образе отказывает. --allow-incomplete предназначен только для
сохранения диагностического неполного пакета; missing и complete=false записаны в манифест.

Wheel-файлы восстановлены из установленных дистрибутивов рабочего venv с новыми RECORD,
не скачаны с PyPI и не выдаются за оригинальные артефакты авторов. Зафиксированы версии,
платформенные теги и хеши. Чистая установка и импорты проверены. При подготовке других ОС
нужны отдельные wheels и бинарники; копирование macOS-venv на Windows/Linux недопустимо.
Windows, Linux, macOS Intel и переустановка Docker на чистом MacBook пока не проверены.
Полный offline означает отсутствие downloads окружения; облачная модель редактора
по подписке всё равно требует сети. Replay/check без модели выполняются локально.
