import asyncio
from datetime import datetime, timedelta, timezone
import json
import uuid
import numpy as np
import redis.asyncio as aioredis
from sqlalchemy import select, update
from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.models.aggregate import EnergyAggregate
from app.models.device import Device, DeviceStatus
from app.models.telemetry import TelemetryReading
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionFactory, async_engine


async def _check_device_connectivity_async():
    await async_engine.dispose()
    logger.info("evaluating_device_connectivity_timeouts")
    threshold_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    async with AsyncSessionFactory() as session:
        query = (
            select(Device)
            .join(Device.operational_status)
            .where(
                Device.is_active.is_(True),
                DeviceStatus.is_online.is_(True),
                (Device.last_seen_at < threshold_time) | (Device.last_seen_at.is_(None)),
            )
        )
        res = await session.execute(query)
        stale_devices = res.scalars().all()

        if not stale_devices:
            return

        redis = await get_redis_client()
        try:
            for device in stale_devices:
                # Update status in PostgreSQL
                stmt = (
                    update(DeviceStatus)
                    .where(DeviceStatus.device_id == device.id)
                    .values(is_online=False, status="OFFLINE", updated_at=datetime.now(timezone.utc))
                )
                await session.execute(stmt)

                # Broadcast device.status_changed event to site WebSocket
                payload = {
                    "event": "device.status_changed",
                    "site_id": str(device.site_id),
                    "device_id": str(device.id),
                    "device_code": device.device_code,
                    "previous_status": "ONLINE",
                    "current_status": "OFFLINE",
                    "reason": "HEARTBEAT_TIMEOUT",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await redis.publish(f"ch:site:{device.site_id}:alerts", json.dumps(payload))
                logger.warn("device_marked_offline_timeout", device_code=device.device_code)

            await session.commit()
        finally:
            await redis.aclose()


async def _rollup_hourly_energy_async():
    """
    Downsamples the previous hour's raw telemetry into energy_aggregates
    using the trapezoidal integration rule.
    """
    await async_engine.dispose()
    now = datetime.now(timezone.utc)
    # Define previous hour window
    period_end = now.replace(minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(hours=1)

    logger.info("running_hourly_energy_rollup", start=period_start.isoformat(), end=period_end.isoformat())

    async with AsyncSessionFactory() as session:
        # Fetch active devices
        devices_res = await session.execute(select(Device.id).where(Device.is_active.is_(True)))
        device_ids = devices_res.scalars().all()

        for device_id in device_ids:
            # Query power readings ordered chronologically
            query = (
                select(TelemetryReading.recorded_at, TelemetryReading.power_kw)
                .where(
                    TelemetryReading.device_id == device_id,
                    TelemetryReading.recorded_at >= period_start,
                    TelemetryReading.recorded_at < period_end,
                    TelemetryReading.power_kw.is_not(None),
                )
                .order_by(TelemetryReading.recorded_at.asc())
            )
            res = await session.execute(query)
            readings = res.all()

            if len(readings) < 2:
                continue

            # Extract timestamps (in seconds) and power values
            timestamps_sec = np.array([r.recorded_at.timestamp() for r in readings], dtype=np.float64)
            power_kw = np.array([r.power_kw for r in readings], dtype=np.float64)

            # Numerical integration via Trapezoidal rule: Integral of P(t) dt in kW*hours
            # np.trapezoid calculates area under the curve in kW * seconds
            energy_seconds = np.trapezoid(power_kw, x=timestamps_sec)
            energy_kwh = float(energy_seconds / 3600.0)

            avg_power = float(np.mean(power_kw))
            peak_power = float(np.max(power_kw))
            min_power = float(np.min(power_kw))

            aggregate = EnergyAggregate(
                id=uuid.uuid4(),
                device_id=device_id,
                period_start=period_start,
                period_end=period_end,
                interval="HOUR",
                energy_consumed_kwh=round(energy_kwh, 4),
                average_power_kw=round(avg_power, 2),
                peak_power_kw=round(peak_power, 2),
                minimum_power_kw=round(min_power, 2),
            )
            session.add(aggregate)

        await session.commit()


@celery_app.task(name="app.workers.scheduled_tasks.check_device_connectivity")
def check_device_connectivity():
    asyncio.run(_check_device_connectivity_async())


@celery_app.task(name="app.workers.scheduled_tasks.rollup_hourly_energy")
def rollup_hourly_energy():
    asyncio.run(_rollup_hourly_energy_async())


@celery_app.task(name="app.workers.scheduled_tasks.purge_expired_raw_telemetry")
def purge_expired_raw_telemetry():
    logger.info("evaluating_expired_monthly_partitions")