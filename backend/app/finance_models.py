"""Finance domain models: price alerts. Market data itself isn't stored
here - it's fetched live from yfinance on demand (finance_data.py) and
not persisted, since historical OHLCV data is cheap to re-fetch and
storing it would just go stale.
"""
import datetime
import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship

from .db import Base


class AlertCondition(str, enum.Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    symbol = Column(String(20), nullable=False, index=True)
    condition = Column(SQLEnum(AlertCondition), nullable=False)
    target_price = Column(Float, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    is_triggered = Column(Boolean, default=False, nullable=False)
    triggered_at = Column(DateTime, nullable=True)
    triggered_price = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


Index("ix_price_alerts_user_active", PriceAlert.user_id, PriceAlert.is_active)