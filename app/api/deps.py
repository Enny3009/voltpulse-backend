from collections.abc import AsyncGenerator
import json
import uuid
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.core.security import decode_token, verify_device_key_constant_time
from app.models.device import Device
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = await get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def get_current_device(
    x_device_code: str = Header(..., description="Unique Device Identification Code"),
    x_device_key: str = Header(..., description="Device Secret Pre-shared Key"),
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> Device:
    # 1. Enforce Rate Limit (1000 requests per 60 seconds)
    limit_key = f"rate_limit:device:{x_device_code}"
    pipe = redis.pipeline(transaction=True)
    pipe.incr(limit_key)
    pipe.ttl(limit_key)
    limit_results = await pipe.execute()
    
    req_count = limit_results[0]
    if req_count == 1 or limit_results[1] < 0:
        await redis.expire(limit_key, 60)
        
    if req_count > 1000:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 1000 requests per minute."
        )

    # 2. Authenticate Device
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

        await redis.set(
            cache_key,
            json.dumps({"device_id": device_id, "credential_hash": credential_hash, "site_id": site_id}),
            ex=600,
        )

    if not verify_device_key_constant_time(credential_hash, x_device_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
        )

    return Device(id=uuid.UUID(device_id), site_id=uuid.UUID(site_id), device_code=x_device_code)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token subject missing",
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = select(User).where(User.id == uuid.UUID(user_id), User.is_active.is_(True))
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


class RoleChecker:
    """Enforces Role-Based Access Control (RBAC)."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action forbidden for role: '{user.role}'. Required: {self.allowed_roles}",
            )
        return user