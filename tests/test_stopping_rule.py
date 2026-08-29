import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.transaction import Transaction, PaymentStatus
from app.models.audit_log import AuditLog
import app.tasks.workers as workers_module

TEST_SYNC_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/revenue_recovery_test"

test_sync_engine = create_engine(TEST_SYNC_DATABASE_URL, echo=False)
TestSyncSessionLocal = sessionmaker(bind=test_sync_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=test_sync_engine)
    yield
    Base.metadata.drop_all(bind=test_sync_engine)


@pytest.fixture(autouse=True)
def patch_sync_session(monkeypatch):
    """Point the worker module's DB session at the test database instead of dev."""
    monkeypatch.setattr(workers_module, "SyncSessionLocal", TestSyncSessionLocal)


def _create_transaction(retry_count: int) -> int:
    with TestSyncSessionLocal() as db:
        txn = Transaction(
            idempotency_key=f"test-stop-{retry_count}-{id(object())}",
            transaction_id="txn_test_stop",
            amount=5000,
            status=PaymentStatus.RETRY_SCHEDULED,
            failure_reason="Customer account balance insufficient for recurring charge",
            retry_count=retry_count,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return txn.id


def test_stopping_rule_triggers_after_max_retries():
    """
    A transaction one attempt away from MAX_RETRIES should, after one more
    forced failure, land in NEEDS_MANUAL_REVIEW instead of scheduling yet
    another retry — proving the stopping rule actually halts the loop.
    """
    transaction_id = _create_transaction(retry_count=workers_module.MAX_RETRIES - 1)

    with patch.object(workers_module, "simulate_gateway_retry", return_value=False):
        with patch.object(workers_module.execute_retry_attempt, "apply_async") as mock_apply_async:
            workers_module.execute_retry_attempt.run(transaction_id)

    with TestSyncSessionLocal() as db:
        txn = db.get(Transaction, transaction_id)
        logs = db.query(AuditLog).filter_by(transaction_id=transaction_id).all()

    assert txn.status == PaymentStatus.NEEDS_MANUAL_REVIEW
    assert txn.retry_count == workers_module.MAX_RETRIES
    mock_apply_async.assert_not_called()
    assert any(log.action == "STOPPING_RULE_TRIGGERED" for log in logs)


def test_retry_reschedules_when_under_max_and_still_failing():
    """
    A transaction below MAX_RETRIES that fails again should be rescheduled
    for another attempt, not escalated.
    """
    transaction_id = _create_transaction(retry_count=0)

    with patch.object(workers_module, "simulate_gateway_retry", return_value=False):
        with patch.object(workers_module.execute_retry_attempt, "apply_async") as mock_apply_async:
            workers_module.execute_retry_attempt.run(transaction_id)

    with TestSyncSessionLocal() as db:
        txn = db.get(Transaction, transaction_id)

    assert txn.status != PaymentStatus.NEEDS_MANUAL_REVIEW
    assert txn.retry_count == 1
    mock_apply_async.assert_called_once()