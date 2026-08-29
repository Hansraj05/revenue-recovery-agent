import asyncio
import httpx
import uuid
import random

BASE_URL = "http://127.0.0.1:8000/api/v1/webhook/payment-failure"
EVENT_COUNT = 50  # Track 3's bar expects a 50+ record batch

TEST_REASONS = [
    "Customer account balance insufficient for recurring charge",
    "Gateway connection timed out after 30000ms",
    "Card reported stolen / invalid account number",
    "Card expired on 08/26",
    "Bank server returned 503 service unavailable",
    "Exceeded daily transaction limit"
]

async def send_event(client, index):
    await asyncio.sleep(index * 0.2)
    payload = {
        "idempotency_key": f"sim-uuid-{uuid.uuid4().hex[:8]}",
        "transaction_id": f"txn_sim_{100 + index}",
        "amount": random.choice([1500, 4900, 9900, 12000, 25000]),
        "failure_reason": random.choice(TEST_REASONS)
    }

    try:
        response = await client.post(BASE_URL, json=payload)
        print(f"Sent Txn {payload['transaction_id']} | Status: {response.status_code}")
    except Exception as e:
        print(f"Failed Txn {payload['transaction_id']} | Error: {e}")

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"🚀 Starting staggered simulation of {EVENT_COUNT} events...")
        tasks = [send_event(client, i) for i in range(EVENT_COUNT)]
        await asyncio.gather(*tasks)
        print("✅ Batch sent! Give Celery a minute to work through retries, then check /analytics.")

if __name__ == "__main__":
    asyncio.run(main())