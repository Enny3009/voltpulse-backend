import json
from fastapi import APIRouter, Depends
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.database import get_db_session
from app.models.alert import Alert
from app.models.device import Device, DeviceStatus
from app.models.site import Site
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
):
    org_id = str(current_user.organization_id)
    cache_key = f"dashboard:summary:{org_id}"

    # 1. Fast path: return Redis cache (<2ms)
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. Slow path: Calculate metrics from PostgreSQL
    # Online & Offline device count
    device_counts_query = (
        select(
            DeviceStatus.is_online,
            func.count(DeviceStatus.device_id).label("count"),
            func.coalesce(func.sum(DeviceStatus.current_power_kw), 0.0).label("total_kw"),
        )
        .join(Device, Device.id == DeviceStatus.device_id)
        .join(Site, Site.id == Device.site_id)
        .where(Site.organization_id == current_user.organization_id)
        .group_by(DeviceStatus.is_online)
    )
    res = await db.execute(device_counts_query)
    rows = res.all()

    online_count = 0
    offline_count = 0
    total_power_kw = 0.0

    for is_online, count, kw in rows:
        if is_online:
            online_count = count
            total_power_kw += kw
        else:
            offline_count = count

    # Active critical alerts count
    alert_query = select(func.count(Alert.id)).where(
        Alert.organization_id == current_user.organization_id,
        Alert.status == "ACTIVE",
        Alert.severity == "CRITICAL",
    )
    alert_res = await db.execute(alert_query)
    critical_alerts = alert_res.scalar() or 0

    data = {
        "organization_id": org_id,
        "total_active_power_kw": round(total_power_kw, 2),
        "online_devices": online_count,
        "offline_devices": offline_count,
        "active_critical_alerts": critical_alerts,
    }

    # Cache for 5 seconds
    await redis.set(cache_key, json.dumps(data), ex=5)
    return data