from datetime import datetime, timezone
import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.core.security import hash_secret
from app.models.device import Device, DeviceCredential, DeviceStatus
from app.models.telemetry import TelemetryReading
from app.models.user import User
from app.schemas.device import (
    DeviceCreateRequest,
    DeviceProvisionResponse,
    DeviceStatusResponse,
    HistoricalTelemetryPoint,
)

router = APIRouter(prefix="/devices", tags=["Hardware & Device Operations"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DeviceProvisionResponse,
    dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER"]))],
)
async def provision_device(
    payload: DeviceCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> DeviceProvisionResponse:
    # Enforce uniqueness of device_code under the site
    existing = await db.execute(
        select(Device).where(
            Device.site_id == payload.site_id,
            Device.device_code == payload.device_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device code '{payload.device_code}' already exists under this site",
        )

    # Generate pre-shared API secret
    raw_secret_key = f"sec_live_{secrets.token_hex(24)}"
    device_id = uuid.uuid4()

    device = Device(
        id=device_id,
        site_id=payload.site_id,
        device_type_id=payload.device_type_id,
        name=payload.name,
        device_code=payload.device_code,
        sampling_rate_seconds=payload.sampling_rate_seconds,
    )
    db.add(device)

    # Hash secret with Argon2
    credential = DeviceCredential(
        device_id=device_id,
        credential_hash=hash_secret(raw_secret_key),
    )
    db.add(credential)

    # Initialize live state tracking row
    dev_status = DeviceStatus(device_id=device_id)
    db.add(dev_status)

    await db.commit()

    return DeviceProvisionResponse(
        id=device.id,
        site_id=device.site_id,
        name=device.name,
        device_code=device.device_code,
        device_key=raw_secret_key,
        created_at=device.created_at,
    )


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
async def get_device_status(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> DeviceStatusResponse:
    res = await db.execute(
        select(DeviceStatus).where(DeviceStatus.device_id == device_id)
    )
    st = res.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return DeviceStatusResponse(
        device_id=st.device_id,
        status=st.status,
        health_score=st.health_score,
        current_power_kw=st.current_power_kw,
        current_temperature=st.current_temperature,
        is_online=st.is_online,
        last_telemetry_at=st.last_telemetry_at,
    )


@router.get("/{device_id}/telemetry", response_model=list[HistoricalTelemetryPoint])
async def get_device_historical_telemetry(
    device_id: uuid.UUID,
    start: datetime = Query(..., description="Start timestamp (UTC)"),
    end: datetime = Query(..., description="End timestamp (UTC)"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[HistoricalTelemetryPoint]:
    """
    Time-bounded query against partitioned hyper-table.
    PostgreSQL executes partition pruning based on `recorded_at` bounds.
    """
    query = (
        select(TelemetryReading)
        .where(
            TelemetryReading.device_id == device_id,
            TelemetryReading.recorded_at >= start,
            TelemetryReading.recorded_at <= end,
        )
        .order_by(desc(TelemetryReading.recorded_at))
        .limit(limit)
    )
    res = await db.execute(query)
    readings = res.scalars().all()

    return [
        HistoricalTelemetryPoint(
            recorded_at=r.recorded_at,
            power_kw=r.power_kw,
            voltage=r.voltage,
            current=r.current,
            temperature=r.temperature,
            frequency=r.frequency,
        )
        for r in readings
    ]