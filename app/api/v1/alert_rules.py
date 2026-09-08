import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.alert import AlertRule
from app.models.user import User
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleResponse

router = APIRouter(prefix="/alert-rules", tags=["Alert Rules"])

@router.post("", status_code=status.HTTP_201_CREATED, response_model=AlertRuleResponse, dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER"]))])
async def create_alert_rule(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AlertRuleResponse:
    rule = AlertRule(
        id=uuid.uuid4(),
        organization_id=current_user.organization_id,
        site_id=payload.site_id,
        device_id=payload.device_id,
        name=payload.name,
        metric=payload.metric,
        condition=payload.condition,
        threshold=payload.threshold,
        severity=payload.severity,
        duration_seconds=payload.duration_seconds,
        is_enabled=payload.is_enabled
    )
    db.add(rule)
    await db.commit()
    return AlertRuleResponse(
        id=rule.id, organization_id=rule.organization_id, site_id=rule.site_id,
        device_id=rule.device_id, name=rule.name, metric=rule.metric,
        condition=rule.condition, threshold=rule.threshold, severity=rule.severity,
        duration_seconds=rule.duration_seconds, is_enabled=rule.is_enabled, created_at=rule.created_at
    )

@router.get("", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AlertRuleResponse]:
    query = select(AlertRule).where(AlertRule.organization_id == current_user.organization_id).limit(limit).offset(offset)
    res = await db.execute(query)
    rules = res.scalars().all()
    return [
        AlertRuleResponse(
            id=r.id, organization_id=r.organization_id, site_id=r.site_id,
            device_id=r.device_id, name=r.name, metric=r.metric,
            condition=r.condition, threshold=r.threshold, severity=r.severity,
            duration_seconds=r.duration_seconds, is_enabled=r.is_enabled, created_at=r.created_at
        ) for r in rules
    ]