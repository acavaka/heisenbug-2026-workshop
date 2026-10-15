# Workshop helpers (Heisenbug / QAI)

| Script | Purpose |
|---|---|
| `up.sh` / `up.ps1` | Create Kind `qai-boutique` + apply Boutique manifests |
| `ports.sh` / `ports.ps1` | Port-forward frontend → http://127.0.0.1:8080 |
| `down.sh` / `down.ps1` | Delete cluster (or `--manifests-only` / `-ManifestsOnly`) |
| `build-and-load-bug1024.sh` | Build+load patched catalog/frontend with BUG-1024 |
| `reproduce-bug-1024.sh` / `.ps1` | Demonstrate product≠cart price divergence |
| `workshop/up-workshop.sh` | Tempo, Grafana, Prometheus, Postgres, Temporal, order-worker |
| `workshop/ports-workshop.sh` | All workshop port-forwards (see docs/sources-and-ports.md) |
| `workshop/verify-stack.sh` | Health + Temporal demos + Tempo traces |
| `workshop/generate-traffic.sh` | Real Boutique browse/cart/checkout → logs + OTEL |
| `workshop/inject-demo-traces.py` | Full multi-service success/error/browse traces in Tempo |
| `offline/export-images.sh` | **Lead:** pull/build once, save `images/*.tar` (USB) |
| `offline/up-offline.sh` | **Participants:** Kind bring-up with **no registry pulls** |

See also `docs/setup-mac.md`, `setup-windows.md`, `sources-and-ports.md`.
