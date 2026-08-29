import random
from celery import shared_task
from app.core.database import SyncSessionLocal
from app.models.transaction import Transaction, PaymentStatus
from app.models.audit_log import AuditLog
from app.services.agent import agent_graph

MAX_RETRIES = 3

# Delays are compressed for demo purposes.
# Production would use countdown=24 * 3600 for the scheduled case.
IMMEDIATE_RETRY_DELAY_SECONDS = 10
SCHEDULED_RETRY_DELAY_SECONDS = 60
BACKOFF_BASE_SECONDS = 15


def _log(db, transaction_id: int, action: str, detail: str):
    db.add(AuditLog(transaction_id=transaction_id, action=action, detail=detail))


def simulate_gateway_retry(failure_reason: str) -> bool:
    """
    Stands in for re-attempting the payment against the (test-mode) gateway.
    We're operating on synthetic data, so this is a weighted outcome rather
    than a real charge attempt.
    """
    return random.random() < 0.55


@shared_task(bind=True)
def evaluate_recovery(self, transaction_id: int):
    """Step 1: classify the failure and decide the initial action."""
    with SyncSessionLocal() as db:
        transaction = db.get(Transaction, transaction_id)
        if not transaction:
            return "Transaction not found"

        try:
            result_state = agent_graph.invoke({
                "transaction_id": transaction_id,
                "failure_reason": transaction.failure_reason,
                "decision": None,
            })
            decision = result_state.get("decision", {})
            action = decision.get("action", "NEEDS_MANUAL_REVIEW")
            explanation = decision.get("explanation", "No explanation returned")
        except Exception as e:
            # An LLM/API hiccup isn't evidence the payment is unrecoverable —
            # escalate for review instead of writing it off as permanent.
            action = "NEEDS_MANUAL_REVIEW"
            explanation = f"Classification failed, escalated for review: {e}"

        _log(db, transaction_id, "AI_CLASSIFICATION", f"{action}: {explanation}")

        if action == "SCHEDULE_RETRY_24H":
            transaction.status = PaymentStatus.RETRY_SCHEDULED
            db.commit()
            execute_retry_attempt.apply_async(args=[transaction_id], countdown=SCHEDULED_RETRY_DELAY_SECONDS)
        elif action == "IMMEDIATE_RETRY":
            transaction.status = PaymentStatus.RETRY_IMMEDIATE
            db.commit()
            execute_retry_attempt.apply_async(args=[transaction_id], countdown=IMMEDIATE_RETRY_DELAY_SECONDS)
        elif action == "NEEDS_MANUAL_REVIEW":
            transaction.status = PaymentStatus.NEEDS_MANUAL_REVIEW
            db.commit()
        else:
            transaction.status = PaymentStatus.PERMANENT_FAILURE
            db.commit()

        return f"{action} applied to transaction {transaction_id}"


@shared_task(bind=True)
def execute_retry_attempt(self, transaction_id: int):
    """Step 2: actually attempt recovery, with a stopping rule on retry count."""
    with SyncSessionLocal() as db:
        transaction = db.get(Transaction, transaction_id)
        if not transaction:
            return "Transaction not found"

        if transaction.retry_count >= MAX_RETRIES:
            transaction.status = PaymentStatus.NEEDS_MANUAL_REVIEW
            _log(db, transaction_id, "STOPPING_RULE_TRIGGERED",
                 f"Reached max retries ({MAX_RETRIES}); escalated for manual review.")
            db.commit()
            return f"Stopping rule hit for transaction {transaction_id}"

        transaction.retry_count += 1
        succeeded = simulate_gateway_retry(transaction.failure_reason)

        if succeeded:
            transaction.status = PaymentStatus.RECOVERED
            _log(db, transaction_id, "RETRY_ATTEMPT",
                 f"Attempt {transaction.retry_count}: succeeded, payment recovered.")
            db.commit()
            return f"Transaction {transaction_id} recovered"

        _log(db, transaction_id, "RETRY_ATTEMPT",
             f"Attempt {transaction.retry_count}: failed.")

        if transaction.retry_count >= MAX_RETRIES:
            transaction.status = PaymentStatus.NEEDS_MANUAL_REVIEW
            _log(db, transaction_id, "STOPPING_RULE_TRIGGERED",
                 f"Reached max retries ({MAX_RETRIES}) after this failure; escalated for manual review.")
            db.commit()
            return f"Transaction {transaction_id} escalated after {transaction.retry_count} attempts"

        db.commit()
        backoff = BACKOFF_BASE_SECONDS * (2 ** (transaction.retry_count - 1))
        execute_retry_attempt.apply_async(args=[transaction_id], countdown=backoff)
        return f"Transaction {transaction_id} retry {transaction.retry_count} failed, backing off {backoff}s"