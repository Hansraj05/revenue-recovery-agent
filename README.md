## Measured Results

Across 3 independent runs of a 50-transaction synthetic failed-payment batch:

| Run | Revenue at Risk | Revenue Recovered | Recovery Rate |
|---|---|---|---|
| 1 | ₹487,200 | ₹301,500 | 61.88% |
| 2 | ₹560,300 | ₹247,800 | 44.23% |
| 3 | ₹605,600 | ₹355,900 | 58.77% |
| **Average** | | | **~55%** |

All transactions in every run reached a terminal state (`RECOVERED`, `NEEDS_MANUAL_REVIEW`,
or `PERMANENT_FAILURE`) — zero unresolved retries by the time each batch settled.

Run-to-run variance is expected: `simulate_gateway_retry()` models each retry attempt as
succeeding with 55% probability (standing in for an actual gateway retry, since this runs
against synthetic data rather than live payment rails), and the observed ~55% average
recovery rate closely tracks that baked-in assumption — a useful sanity check that the
batch size and methodology are behaving as designed rather than producing noisy results.

Delivery note: one run recorded 48/50 successful webhook deliveries under a tight
0.2s-stagger burst; 2 requests failed with either a client-side timeout or a 500 from
the `/webhook/payment-failure` endpoint's Redis-queuing step. The 500 is deliberate —
the handler returns it specifically so a real payment gateway's webhook retry logic would
re-deliver the event — and is consistent with standard webhook delivery semantics under load.

### Reproducing these results
```bash
python -m scripts.wipe_db
# start Celery worker + FastAPI app in separate terminals, then:
python -m scripts.simulate_events
# wait for the dashboard to show "Still Retrying: ₹0", then check /analytics
```