from datetime import datetime
from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    idempotency_key: str = Field(..., description="Unique ID for the failure event")
    transaction_id: str
    amount: int = Field(..., gt=0, description="Amount in lowest currency unit")
    failure_reason: str


class TransactionResponse(BaseModel):
    id: int
    idempotency_key: str
    transaction_id: str
    amount: int
    status: str
    failure_reason: str
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    transaction_id: int
    action: str
    detail: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyticsResponse(BaseModel):
    total_transactions: int
    total_revenue_at_risk: int
    total_revenue_recovered: int
    total_revenue_recovering: int
    total_revenue_under_review: int
    total_revenue_lost: int
    recovery_rate_percentage: float
    status_breakdown: dict[str, int]