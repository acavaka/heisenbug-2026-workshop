# Release v0.10.0-workshop

Date: 2026-09-15

## Changes

- Workshop overlays: Tempo, Temporal order-worker
- Experiment: increased `GATEWAY_TIMEOUT` on frontend ingress path (may hide slow payment and encourage client retries)
- Catalog price admin endpoint on :8081

## Known risks

- Client-side Pay retry without idempotent WorkflowId → BUG-TEMP-02 class
- Payment timeout + new idempotency key → INC-2088 class
