"""Price alert endpoints. Not capability tools (see finance_tools.py's
docstring for why) but gated through the same security_gateway check —
creating/deleting an alert needs trading_enabled on, same as the tools.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .finance_models import PriceAlert, AlertCondition
from .capability_system import PermissionLevel
from .security_gateway import check_permission
from .security_models import GatewayDecision
from .auth import get_current_active_user
from .models import User
from .db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/finance", tags=["finance"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PriceAlertCreate(BaseModel):
    symbol: str
    condition: AlertCondition
    target_price: float


def _gate(db: Session, user_id: int, tool_name: str, permission_level: PermissionLevel, target: Optional[str] = None):
    result = check_permission(db, user_id, tool_name, domain="finance", permission_level=permission_level, target_path=target)
    if result.decision == GatewayDecision.BLOCKED:
        raise HTTPException(status_code=403, detail=f"Blocked by Security Gateway: {result.reason}")
    if result.decision == GatewayDecision.NEEDS_CONFIRMATION:
        raise HTTPException(status_code=409, detail=f"Requires confirmation: {result.reason}")


@router.post("/alerts")
def create_alert(
    payload: PriceAlertCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _gate(db, current_user.id, "create_price_alert", PermissionLevel.SAFE_ACTION, target=payload.symbol)

    alert = PriceAlert(
        user_id=current_user.id,
        symbol=payload.symbol.upper(),
        condition=payload.condition,
        target_price=payload.target_price,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_to_dict(alert)


@router.get("/alerts")
def list_alerts(
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _gate(db, current_user.id, "list_price_alerts", PermissionLevel.READ_ONLY)

    query = db.query(PriceAlert).filter(PriceAlert.user_id == current_user.id)
    if active_only:
        query = query.filter(PriceAlert.is_active == True)  # noqa: E712
    alerts = query.order_by(PriceAlert.created_at.desc()).all()
    return {"items": [_alert_to_dict(a) for a in alerts], "count": len(alerts)}


@router.delete("/alerts/{alert_id}")
def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _gate(db, current_user.id, "delete_price_alert", PermissionLevel.SAFE_ACTION)

    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    db.delete(alert)
    db.commit()
    return {"success": True}


@router.post("/alerts/check")
def check_alerts_now(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Manually trigger an alert check (no scheduler wired up yet — see
    the caveat in the handoff message). Fetches a live quote for every
    active alert's symbol and flips is_triggered if the condition is met.
    """
    _gate(db, current_user.id, "check_price_alerts", PermissionLevel.READ_ONLY)

    from . import finance_data
    import datetime

    alerts = db.query(PriceAlert).filter(
        PriceAlert.user_id == current_user.id,
        PriceAlert.is_active == True,  # noqa: E712
        PriceAlert.is_triggered == False,  # noqa: E712
    ).all()

    triggered = []
    for alert in alerts:
        try:
            quote = finance_data.get_quote(alert.symbol)
        except finance_data.MarketDataError:
            continue
        price = quote.get("price")
        if price is None:
            continue

        hit = (alert.condition == AlertCondition.ABOVE and price >= alert.target_price) or \
              (alert.condition == AlertCondition.BELOW and price <= alert.target_price)

        if hit:
            alert.is_triggered = True
            alert.triggered_at = datetime.datetime.utcnow()
            alert.triggered_price = price
            triggered.append(_alert_to_dict(alert))

    db.commit()
    return {"checked": len(alerts), "triggered": triggered}


def _alert_to_dict(a: PriceAlert) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "condition": a.condition.value,
        "target_price": a.target_price,
        "is_active": a.is_active,
        "is_triggered": a.is_triggered,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "triggered_price": a.triggered_price,
        "created_at": a.created_at.isoformat(),
    }