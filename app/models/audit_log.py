from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models.transaction import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    action = Column(String, nullable=False)    # e.g. AI_CLASSIFICATION, RETRY_ATTEMPT, STOPPING_RULE_TRIGGERED
    detail = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())