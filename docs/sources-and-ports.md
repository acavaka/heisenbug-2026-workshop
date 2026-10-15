# Sources and local ports

Port-forward (держать в отдельном терминале):

```bash
cd microservices-demo
./hack/workshop/ports-workshop.sh
```

Подготовка нового стенда: [prework и строгий USB-маршрут](participant-prework-draft.md).
Для port-forward используйте kubeconfig своего подготовленного стенда.

Read-only готовность: [prework](participant-prework-draft.md).

## Адреса

| Service | URL | Notes |
|---|---|---|
| Boutique frontend | http://127.0.0.1:8080 | UI |
| Catalog admin | http://127.0.0.1:8081 | BUG-1024 (если plant) |
| Grafana | http://127.0.0.1:3000 | `admin`/`admin`; Explore → **Tempo** |
| Tempo HTTP | http://127.0.0.1:3200 | `/ready` |
| Tempo OTLP gRPC/HTTP | `:4317` / `:4318` | OTEL / inject |
| Prometheus | http://127.0.0.1:9090 | |
| Temporal UI | http://127.0.0.1:8233 | |
| Temporal gRPC | `127.0.0.1:7233` | skill |
| order-worker | http://127.0.0.1:8088 | `/orders`, `/stuck`, `/duplicate` |
| Postgres | `127.0.0.1:5432` | `postgres`/`workshop`, db `orders` |

## Read-only проверка HTTP

```bash
# health
curl -s http://127.0.0.1:8088/healthz
curl -s http://127.0.0.1:3200/ready

```

Учебные события и namespace подготавливает ведущий. Не выполняйте POST-запросы,
создающие заказы/workflow, для проверки готовности или расследования.

## Agent `.env`

```text
TEMPO_URL=http://127.0.0.1:3200
PROM_URL=http://127.0.0.1:9090
TEMPORAL_HOST=127.0.0.1:7233
```
