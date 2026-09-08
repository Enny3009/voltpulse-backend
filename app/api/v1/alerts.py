from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.alert import Alert
from app.models.user import User
from app.schemas.alert import AlertActionResponse, AlertResponse

router = APIRouter(prefix="/alerts", tags=["Incident Management"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    status_filter: str | None = Query(None, description="ACTIVE, ACKNOWLEDGED, RESOLVED"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AlertResponse]:
    query = (
        select(Alert)
        .where(Alert.organization_id == current_user.organization_id)
        .order_by(desc(Alert.triggered_at))
        .limit(limit)
    )
    if status_filter:
        query = query.where(Alert.status == status_filter)

    res = await db.execute(query)
    alerts = res.scalars().all()

    return [
        AlertResponse(
            id=a.id,
            device_id=a.device_id,
            metric=a.metric,
            actual_value=a.actual_value,
            threshold=a.threshold,
            severity=a.severity,
            status=a.status,
            message=a.message,
            triggered_at=a.triggered_at,
            acknowledged_at=a.acknowledged_at,
            resolved_at=a.resolved_at,
        )
        for a in alerts
    ]


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertActionResponse,
    dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER", "OPERATOR"]))],
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AlertActionResponse:
    res = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = res.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.id
    await db.commit()

    return AlertActionResponse(
        alert_id=alert.id,
        status=alert.status,
        updated_at=alert.acknowledged_at,
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertActionResponse,
    dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER"]))],
)
async def resolve_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AlertActionResponse:
    res = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = res.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = "RESOLVED"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.id
    await db.commit()

    return AlertActionResponse(
        alert_id=alert.id,
        status=alert.status,
        updated_at=alert.resolved_at,
    )