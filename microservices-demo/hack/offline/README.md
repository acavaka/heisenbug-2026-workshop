# Offline Kind pack (пакет образов)

На дне воркшопа участники **не** качают образы из `gcr.io` / Docker Hub.
Ведущий один раз готовит tar-архив и раздаёт на USB / шару.

## Файлы

```text
hack/offline/
  image-list.txt           # что входит в пакет
  export-images.sh         # ВЕДУЩИЙ: pull/build + docker save (нужна сеть)
  save-from-kind.sh        # альтернатива, если Kind уже поднят
  load-images.sh           # docker load + kind load (офлайн)
  generate-manifests.sh    # boutique/* + imagePullPolicy: Never
  up-offline.sh            # полный офлайн-подъём
  images/                  # *.tar (gitignore)
  workshop-images.tar.gz   # один файл для USB (gitignore)
  README.md                # этот файл
```

Типичный размер: **~1.6 GB** (`workshop-images.tar.gz`), распакованные tar ~**4.8 GB**.

---

## Ведущий — подготовка (один раз)

1. Docker Desktop запущен, есть сеть.

```bash
cd microservices-demo
chmod +x hack/offline/*.sh
./hack/offline/export-images.sh
```

2. Проверьте:

```bash
ls -lh hack/offline/workshop-images.tar.gz
ls hack/offline/images/*.tar | wc -l   # ожидайте ~23
```

3. Скопируйте **`workshop-images.tar.gz`** на USB / внутреннюю шару.  
   **Не коммитьте** tar в GitHub.

4. Перед залом у себя:

```bash
./hack/offline/up-offline.sh
./hack/workshop/ports-workshop.sh
# пройти docs/manual-testing.md целиком
```

---

## Участник — день воркшопа

1. Репозиторий уже склонирован/распакован, Docker + kind + kubectl установлены (см. setup-mac / setup-windows).  
2. Положите архив от ведущего:

```bash
# путь примерный
cp /media/usb/workshop-images.tar.gz microservices-demo/hack/offline/
```

3. Подъём (Mac или **Git Bash** на Windows):

```bash
cd microservices-demo
./hack/offline/up-offline.sh
# другое окно:
./hack/workshop/ports-workshop.sh
```

4. Ручные проверки: [docs/manual-testing.md](../../../docs/manual-testing.md).

---

## Что внутри пакета

- Kind node (`kindest/node`)  
- Все сервисы Online Boutique (`boutique/*:v0.10.0`) + redis, busybox  
- Tempo, Grafana, Prometheus, Postgres, Temporal, Temporal UI  
- `order-worker` + образы **BUG-1024** (catalog/frontend workshop)

Манифесты при `up-offline` переписываются на `boutique/...` и `imagePullPolicy: Never`.

---

## Онлайн-режим (не для зала)

`./hack/up.sh` + `./hack/workshop/up-workshop.sh` — тянут реестры, удобно дома у ведущего при разработке.
