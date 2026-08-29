from enum import Enum as PyEnum
from sqlalchemy import Column, String, Integer, Enum, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class PaymentStatus(str, PyEnum):
    FAILED = "FAILED"
    EVALUATING = "EVALUATING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RETRY_IMMEDIATE = "RETRY_IMMEDIATE"
    RECOVERED = "RECOVERED"
    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    transaction_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.FAILED, nullable=False)
    failure_reason = Column(String, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())