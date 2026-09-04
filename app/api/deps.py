from collections.abc import AsyncGenerator
import json
import uuid
from fastapi import Depends, Header, HTTPException, status
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.core.security import verify_device_key_constant_time
from app.models.device import Device, DeviceCredential


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = await get_redis_client()
    try:
        yield client
    finally:
        await client.close()


async def get_current_device(
    x_device_code: str = Header(..., description="Unique Device Identification Code"),
    x_device_key: str = Header(..., description="Device Secret Pre-shared Key"),
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> Device:
    """
    Authenticates hardware devices. 
    Caches valid credential hashes in Redis for 10 minutes to minimize DB queries.
    """
    cache_key = f"cache:device:auth:{x_device_code}"
    cached_auth = await redis.get(cache_key)

    device_id: str
    credential_hash: str
    site_id: str

    if cached_auth:
        auth_data = json.loads(cached_auth)
        device_id = auth_data["device_id"]
        credential_hash = auth_data["credential_hash"]
        site_id = auth_data["site_id"]
    else:
        query = (
            select(Device)
            .options(selectinload(Device.credential))
            .where(Device.device_code == x_device_code, Device.is_active.is_(True))
        )
        result = await db.execute(query)
        device = result.scalar_one_or_none()

        if not device or not device.credential or not device.credential.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials or device is inactive",
            )

        device_id = str(device.id)
        credential_hash = device.credential.credential_hash
        site_id = str(device.site_id)

        # Cache credentials for fast authentication on subsequent requests
        await redis.set(
            cache_key,
            json.dumps({
                "device_id": device_id,
                "credential_hash": credential_hash,
                "site_id": site_id,
            }),
            ex=600,
        )

    # Constant-time hash check
    if not verify_device_key_constant_time(credential_hash, x_device_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
        )

    # Construct lightweight device context
    device_obj = Device(
        id=uuid.UUID(device_id),
        site_id=uuid.UUID(site_id),
        device_code=x_device_code,
    )
    return device_obj