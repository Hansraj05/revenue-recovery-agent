import asyncio
import os
import random
import uuid

import httpx

# Point at the deployed API by setting WEBHOOK_URL, e.g.
#   https://revenue-recovery-api.onrender.com/api/v1/webhook/payment-failure
BASE_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/api/v1/webhook/payment-failure")
HEALTH_URL = BASE_URL.split("/api/v1")[0] + "/health"
EVENT_COUNT = 50
STAGGER_SECONDS = float(os.getenv("STAGGER_SECONDS", "0.2"))

TEST_REASONS = [
    "Customer account balance insufficient for recurring charge",
    "Gateway connection timed out after 30000ms",
    "Card reported stolen / invalid account number",
    "Card expired on 08/26",
    "Bank server returned 503 service unavailable",
    "Exceeded daily transaction limit",
]


async def wake_up(client):
    """Free Render services sleep when idle; ping /health until the API answers."""
    print("Waking up the API (can take ~60s on a free Render instance)...")
    for _ in range(12):
        try:
            r = await client.get(HEALTH_URL, timeout=30.0)
            if r.status_code == 200:
                print("API is awake.")
                return
        except Exception:
            pass
        await asyncio.sleep(5)
    print("Warning: API did not answer /health; continuing anyway.")


async def send_event(client, index):
    await asyncio.sleep(index * STAGGER_SECONDS)
    payload = {
        "idempotency_key": f"sim-uuid-{uuid.uuid4().hex[:8]}",
        "transaction_id": f"txn_sim_{100 + index}",
        "amount": random.choice([1500, 4900, 9900, 12000, 25000]),
        "failure_reason": random.choice(TEST_REASONS),
    }
    try:
        response = await client.post(BASE_URL, json=payload)
        print(f"Sent Txn {payload['transaction_id']} | Status: {response.status_code}")
    except Exception as e:
        print(f"Failed Txn {payload['transaction_id']} | Error: {e}")


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        await wake_up(client)
        print(f"Starting staggered simulation of {EVENT_COUNT} events...")
        await asyncio.gather(*[send_event(client, i) for i in range(EVENT_COUNT)])
        print("Batch sent! Give the worker a few minutes, then check /analytics.")


if __name__ == "__main__":
    asyncio.run(main())