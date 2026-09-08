import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["Sites"])

@router.post("", status_code=status.HTTP_201_CREATED, response_model=SiteResponse, dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER"]))])
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SiteResponse:
    existing = await db.execute(
        select(Site).where(Site.organization_id == current_user.organization_id, Site.code == payload.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Site code already exists")

    site = Site(
        id=uuid.uuid4(), organization_id=current_user.organization_id,
        code=payload.code, name=payload.name, address=payload.address,
        latitude=payload.latitude, longitude=payload.longitude, timezone=payload.timezone
    )
    db.add(site)
    await db.commit()
    
    return SiteResponse(
        id=site.id, organization_id=site.organization_id, code=site.code,
        name=site.name, address=site.address, 
        latitude=float(site.latitude) if site.latitude else None,
        longitude=float(site.longitude) if site.longitude else None,
        timezone=site.timezone, is_active=site.is_active, created_at=site.created_at
    )

@router.get("", response_model=list[SiteResponse])
async def list_sites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[SiteResponse]:
    query = select(Site).where(Site.organization_id == current_user.organization_id).limit(limit).offset(offset)
    res = await db.execute(query)
    sites = res.scalars().all()

    return [
        SiteResponse(
            id=s.id, organization_id=s.organization_id, code=s.code, name=s.name,
            address=s.address, latitude=float(s.latitude) if s.latitude else None,
            longitude=float(s.longitude) if s.longitude else None,
            timezone=s.timezone, is_active=s.is_active, created_at=s.created_at
        ) for s in sites
    ]