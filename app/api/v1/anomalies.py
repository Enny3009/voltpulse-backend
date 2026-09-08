import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.anomaly import Anomaly
from app.models.device import Device
from app.models.site import Site
from app.models.user import User
from app.schemas.anomaly import AnomalyResponse, AnomalyUpdate

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])

@router.get("", response_model=list[AnomalyResponse])
async def list_anomalies(
    device_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AnomalyResponse]:
    query = (
        select(Anomaly)
        .join(Device, Anomaly.device_id == Device.id)
        .join(Site, Device.site_id == Site.id)
        .where(Site.organization_id == current_user.organization_id)
        .order_by(desc(Anomaly.detected_at))
    )
    
    if device_id:
        query = query.where(Anomaly.device_id == device_id)
    if status_filter:
        query = query.where(Anomaly.status == status_filter)
        
    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    anomalies = res.scalars().all()
    
    return [
        AnomalyResponse(
            id=a.id, device_id=a.device_id, metric=a.metric,
            value=a.value, expected_value=a.expected_value,
            deviation_score=a.deviation_score, algorithm=a.algorithm,
            severity=a.severity, detected_at=a.detected_at, status=a.status
        ) for a in anomalies
    ]

@router.patch("/{anomaly_id}", response_model=AnomalyResponse, dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER", "OPERATOR"]))])
async def update_anomaly_status(
    anomaly_id: uuid.UUID,
    payload: AnomalyUpdate,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> AnomalyResponse:
    res = await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    anomaly = res.scalar_one_or_none()
    
    if not anomaly:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")
        
    anomaly.status = payload.status
    await db.commit()
    
    return AnomalyResponse(
        id=anomaly.id, device_id=anomaly.device_id, metric=anomaly.metric,
        value=anomaly.value, expected_value=anomaly.expected_value,
        deviation_score=anomaly.deviation_score, algorithm=anomaly.algorithm,
        severity=anomaly.severity, detected_at=anomaly.detected_at, status=anomaly.status
    )