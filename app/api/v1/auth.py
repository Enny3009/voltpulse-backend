from datetime import datetime, timezone
import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import create_access_token, hash_secret, verify_secret
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import TokenRefreshRequest, TokenResponse, UserLoginRequest, UserProfileResponse, UserRegisterRequest

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])

async def issue_tokens(user_id: str, redis: aioredis.Redis) -> TokenResponse:
    access_token = create_access_token(subject=user_id)
    refresh_token = secrets.token_urlsafe(64)
    
    # Store refresh token in Redis with 7-day expiration
    await redis.set(
        f"refresh_token:{refresh_token}", 
        user_id, 
        ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def register_organization_and_admin(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenResponse:
    slug_check = await db.execute(select(Organization).where(Organization.slug == payload.organization_slug))
    if slug_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug already exists")

    org = Organization(id=uuid.uuid4(), name=payload.organization_name, slug=payload.organization_slug)
    db.add(org)
    await db.flush()

    admin_user = User(
        id=uuid.uuid4(), organization_id=org.id, email=payload.email,
        password_hash=hash_secret(payload.password), first_name=payload.first_name,
        last_name=payload.last_name, role="ADMIN"
    )
    db.add(admin_user)
    await db.commit()

    return await issue_tokens(str(admin_user.id), redis)

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenResponse:
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()

    if not user or not verify_secret(user.password_hash, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return await issue_tokens(str(user.id), redis)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: TokenRefreshRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenResponse:
    user_id = await redis.get(f"refresh_token:{payload.refresh_token}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
        
    # Rotate token: delete old, issue new
    await redis.delete(f"refresh_token:{payload.refresh_token}")
    return await issue_tokens(user_id, redis)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: TokenRefreshRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    await redis.delete(f"refresh_token:{payload.refresh_token}")

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(
        id=current_user.id, organization_id=current_user.organization_id,
        email=current_user.email, first_name=current_user.first_name,
        last_name=current_user.last_name, role=current_user.role,
        is_active=current_user.is_active, created_at=current_user.created_at
    )