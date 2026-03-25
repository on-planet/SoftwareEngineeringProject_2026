from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth_user import AuthUser
from app.routers.auth import get_current_user
from app.schemas.common import IdOut
from app.schemas.user_alerts import (
    AlertCenterOut,
    AlertRuleCreateIn,
    AlertRuleEvaluationOut,
    AlertRuleOut,
    AlertRuleUpdateIn,
)
from app.services.user_alerts_service import (
    create_alert_rule,
    delete_alert_rule,
    get_alert_center,
    list_alert_rules,
    update_alert_rule,
)

router = APIRouter(tags=["user_alerts"])


@router.get("/user/me/alerts", response_model=list[AlertRuleOut])
def list_my_alert_rules(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_alert_rules(db, int(current_user.id))


@router.get("/user/me/alerts/center", response_model=AlertCenterOut)
def get_my_alert_center(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return get_alert_center(db, int(current_user.id))


@router.post("/user/me/alerts", response_model=AlertRuleOut)
def create_my_alert_rule(
    payload: AlertRuleCreateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return create_alert_rule(db, int(current_user.id), payload)


@router.patch("/user/me/alerts/{rule_id}", response_model=AlertRuleOut)
def update_my_alert_rule(
    rule_id: int,
    payload: AlertRuleUpdateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    item = update_alert_rule(db, int(current_user.id), rule_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return item


@router.delete("/user/me/alerts/{rule_id}", response_model=IdOut)
def delete_my_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ok = delete_alert_rule(db, int(current_user.id), rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"id": rule_id}
