# TestOps — recent runs (fixture)

| Run | Suite | Result | Linked |
|---|---|---|---|
| TO-4412 | checkout e2e | FAILED | INC-2088 |
| TO-4410 | catalog price | FAILED | BUG-1024 |
| TO-4408 | order saga | FAILED | BUG-TEMP-01 |
| TO-4401 | smoke | PASSED | — |

## Notes

- TO-4412: two Charge spans, different payment_id
- TO-4408: Ship activity retry count > 50 in Temporal
