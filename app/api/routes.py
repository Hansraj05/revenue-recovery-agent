from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from app.tasks.celery_app import celery_app
from app.core.database import get_db
from app.schemas.payment import (
    WebhookPayload, TransactionResponse, AnalyticsResponse, AuditLogResponse
)
from app.models.transaction import Transaction, PaymentStatus
from app.models.audit_log import AuditLog
from app.tasks.workers import evaluate_recovery

router = APIRouter()


@router.post("/webhook/payment-failure", status_code=status.HTTP_202_ACCEPTED)
async def handle_payment_failure(payload: WebhookPayload, db: AsyncSession = Depends(get_db)):
    new_txn = Transaction(
        idempotency_key=payload.idempotency_key,
        transaction_id=payload.transaction_id,
        amount=payload.amount,
        failure_reason=payload.failure_reason,
        status=PaymentStatus.FAILED
    )

    try:
        db.add(new_txn)
        await db.commit()
        await db.refresh(new_txn)
    except IntegrityError:
        await db.rollback()
        return {"msg": "Webhook already processed", "idempotency_key": payload.idempotency_key}

    try:
        await run_in_threadpool(evaluate_recovery.delay, new_txn.id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Redis queuing failed. Gateway should retry. Error: {str(e)}"
        )

    return {"msg": "Failure recorded and evaluation started", "transaction_db_id": new_txn.id}


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction).order_by(Transaction.id.desc()))
    return result.scalars().all()


@router.get("/transactions/{transaction_id}/audit", response_model=list[AuditLogResponse])
async def get_transaction_audit_trail(transaction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()
    if not logs:
        raise HTTPException(status_code=404, detail="No audit trail found for this transaction")
    return logs


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction))
    transactions = result.scalars().all()

    total_txns = len(transactions)
    if total_txns == 0:
        return AnalyticsResponse(
            total_transactions=0,
            total_revenue_at_risk=0,
            total_revenue_recovered=0,
            total_revenue_recovering=0,
            total_revenue_under_review=0,
            total_revenue_lost=0,
            recovery_rate_percentage=0.0,
            status_breakdown={}
        )

    total_at_risk = sum(t.amount for t in transactions)
    recovered = sum(t.amount for t in transactions if t.status == PaymentStatus.RECOVERED)
    recovering = sum(
        t.amount for t in transactions
        if t.status in [PaymentStatus.RETRY_SCHEDULED, PaymentStatus.RETRY_IMMEDIATE]
    )
    under_review = sum(t.amount for t in transactions if t.status == PaymentStatus.NEEDS_MANUAL_REVIEW)
    lost = sum(t.amount for t in transactions if t.status == PaymentStatus.PERMANENT_FAILURE)

    breakdown = {}
    for t in transactions:
        status_key = str(t.status.value if hasattr(t.status, "value") else t.status)
        breakdown[status_key] = breakdown.get(status_key, 0) + 1

    # Actual $ recovered ÷ total at risk — not "currently retrying"
    recovery_rate = round((recovered / total_at_risk * 100), 2) if total_at_risk > 0 else 0.0

    return AnalyticsResponse(
        total_transactions=total_txns,
        total_revenue_at_risk=total_at_risk,
        total_revenue_recovered=recovered,
        total_revenue_recovering=recovering,
        total_revenue_under_review=under_review,
        total_revenue_lost=lost,
        recovery_rate_percentage=recovery_rate,
        status_breakdown=breakdown
    )