import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models.aggregate import EnergyAggregate
from app.models.device import Device
from app.models.site import Site
from app.models.user import User
from app.schemas.analytics import EnergyAggregateResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/devices/{device_id}", response_model=list[EnergyAggregateResponse])
async def get_device_analytics(
    device_id: uuid.UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("HOUR"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[EnergyAggregateResponse]:
    
    auth_check = await db.execute(
        select(Device).join(Site).where(
            Device.id == device_id,
            Site.organization_id == current_user.organization_id
        )
    )
    if not auth_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    query = select(EnergyAggregate).where(
        EnergyAggregate.device_id == device_id,
        EnergyAggregate.interval == interval,
        EnergyAggregate.period_start >= start,
        EnergyAggregate.period_end <= end
    ).order_by(EnergyAggregate.period_start.asc())
    
    res = await db.execute(query)
    aggregates = res.scalars().all()
    
    return [
        EnergyAggregateResponse(
            id=a.id, device_id=a.device_id, period_start=a.period_start,
            period_end=a.period_end, interval=a.interval,
            energy_consumed_kwh=a.energy_consumed_kwh,
            average_power_kw=a.average_power_kw, peak_power_kw=a.peak_power_kw,
            minimum_power_kw=a.minimum_power_kw
        ) for a in aggregates
    ]