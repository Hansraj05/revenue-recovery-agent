import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select

from main import app
from app.core.database import get_db
from app.models import Base
from app.models.transaction import Transaction

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/revenue_recovery_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown_db():
    app.dependency_overrides[get_db] = override_get_db
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_creates_only_one_transaction():
    """
    Sends the same webhook payload (same idempotency_key) twice.
    Only one Transaction row should exist afterward — the second request
    should be recognized as a duplicate, not create a second row.
    """
    payload = {
        "idempotency_key": "test-idem-key-001",
        "transaction_id": "txn_test_001",
        "amount": 5000,
        "failure_reason": "Customer account balance insufficient for recurring charge",
    }

    # Mock the Celery dispatch — this test is about the DB-level idempotency
    # guarantee, not the recovery pipeline, so we don't want a real Redis call.
    with patch("app.api.routes.evaluate_recovery.delay", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first_response = await client.post("/api/v1/webhook/payment-failure", json=payload)
            second_response = await client.post("/api/v1/webhook/payment-failure", json=payload)

    # Both return 202 — FastAPI applies the route's fixed status_code to every
    # plain-dict return from this endpoint, so the distinguishing signal is the
    # message body, not the status code.
    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["msg"] == "Webhook already processed"

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.idempotency_key == payload["idempotency_key"])
        )
        matching_transactions = result.scalars().all()

    assert len(matching_transactions) == 1