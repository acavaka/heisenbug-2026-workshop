# Online Boutique — runbook map

| Symptom | First skill | Tracker |
|---|---|---|
| PDP price ≠ cart | kubectl logs catalog, code cache | BUG-1024 |
| Double charge | Tempo + postgres payments | INC-2088 |
| SHIPPING_PENDING forever | temporal_inspect, Temporal UI | BUG-TEMP-01 |
| Double Pay workflows | temporal_inspect | BUG-TEMP-02 |
| UI paid / DB PENDING | postgres_query | BUG-DB-01 |
| Empty cart | redis / cartservice logs | BUG-REDIS-01 |
| Bad currency | currencyservice | BUG-CURR-01 |
| Bad shipping quote | shippingservice + Tempo | BUG-SHIP-01 |
| Weird recommendations | recommendationservice | BUG-REC-01 |
| Post-release latency | github release notes + prom | BUG-REL-01 |

## Stack endpoints

See [docs/sources-and-ports.md](../../docs/sources-and-ports.md).
