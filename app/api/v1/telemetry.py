import json
import uuid
from fastapi import APIRouter, Depends, status
import redis.asyncio as aioredis
from app.api.deps import get_current_device, get_redis
from app.core.config import settings
from app.core.redis import STREAM_TELEMETRY_RAW
from app.models.device import Device
from app.schemas.telemetry import (
    TelemetryBatchPayload,
    TelemetryIngestResponse,
    TelemetryPayload,
)

router = APIRouter(prefix="/telemetry", tags=["Telemetry Ingestion"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TelemetryIngestResponse,
    summary="Ingest a single telemetry reading",
)
async def ingest_telemetry(
    payload: TelemetryPayload,
    device: Device = Depends(get_current_device),
    redis: aioredis.Redis = Depends(get_redis),
) -> TelemetryIngestResponse:
    device_id_str = str(device.id)
    site_id_str = str(device.site_id)
    reading_id = str(uuid.uuid4())

    data_dict = {
        "id": reading_id,
        "device_id": device_id_str,
        "site_id": site_id_str,
        "recorded_at": payload.recorded_at.isoformat(),
        "voltage": payload.voltage if payload.voltage is not None else "",
        "current": payload.current if payload.current is not None else "",
        "power_kw": payload.power_kw if payload.power_kw is not None else "",
        "energy_kwh": payload.energy_kwh if payload.energy_kwh is not None else "",
        "temperature": payload.temperature if payload.temperature is not None else "",
        "pressure": payload.pressure if payload.pressure is not None else "",
        "frequency": payload.frequency if payload.frequency is not None else "",
        "power_factor": payload.power_factor if payload.power_factor is not None else "",
        "runtime_seconds": payload.runtime_seconds if payload.runtime_seconds is not None else "",
        "metadata": json.dumps(payload.metadata),
    }

    # Atomic pipeline: Append to Stream + Update Live Hash State
    pipe = redis.pipeline(transaction=False)
    pipe.xadd(
        name=STREAM_TELEMETRY_RAW,
        fields=data_dict,
        maxlen=settings.REDIS_STREAM_MAXLEN,
        approximate=True,
    )
    # Update live operational state
    pipe.hset(
        name=f"device:live:{device_id_str}",
        mapping={
            "status": "ONLINE",
            "last_seen_at": payload.recorded_at.isoformat(),
            "power_kw": str(payload.power_kw or 0.0),
            "temperature": str(payload.temperature or 0.0),
        },
    )
    pipe.expire(f"device:live:{device_id_str}", 300)
    results = await pipe.execute()

    return TelemetryIngestResponse(event_id=results[0], batch_count=1)


@router.post(
    "/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TelemetryIngestResponse,
    summary="Ingest a micro-batch of telemetry readings (up to 500)",
)
async def ingest_telemetry_batch(
    payload: TelemetryBatchPayload,
    device: Device = Depends(get_current_device),
    redis: aioredis.Redis = Depends(get_redis),
) -> TelemetryIngestResponse:
    device_id_str = str(device.id)
    site_id_str = str(device.site_id)

    pipe = redis.pipeline(transaction=False)
    latest_reading = payload.readings[-1]

    for reading in payload.readings:
        reading_id = str(uuid.uuid4())
        data_dict = {
            "id": reading_id,
            "device_id": device_id_str,
            "site_id": site_id_str,
            "recorded_at": reading.recorded_at.isoformat(),
            "voltage": reading.voltage if reading.voltage is not None else "",
            "current": reading.current if reading.current is not None else "",
            "power_kw": reading.power_kw if reading.power_kw is not None else "",
            "energy_kwh": reading.energy_kwh if reading.energy_kwh is not None else "",
            "temperature": reading.temperature if reading.temperature is not None else "",
            "pressure": reading.pressure if reading.pressure is not None else "",
            "frequency": reading.frequency if reading.frequency is not None else "",
            "power_factor": reading.power_factor if reading.power_factor is not None else "",
            "runtime_seconds": reading.runtime_seconds if reading.runtime_seconds is not None else "",
            "metadata": json.dumps(reading.metadata),
        }
        pipe.xadd(
            name=STREAM_TELEMETRY_RAW,
            fields=data_dict,
            maxlen=settings.REDIS_STREAM_MAXLEN,
            approximate=True,
        )

    # Update live operational state from the latest reading in the batch
    pipe.hset(
        name=f"device:live:{device_id_str}",
        mapping={
            "status": "ONLINE",
            "last_seen_at": latest_reading.recorded_at.isoformat(),
            "power_kw": str(latest_reading.power_kw or 0.0),
            "temperature": str(latest_reading.temperature or 0.0),
        },
    )
    pipe.expire(f"device:live:{device_id_str}", 300)
    await pipe.execute()

    return TelemetryIngestResponse(batch_count=len(payload.readings))