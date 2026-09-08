import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationResponse, OrganizationUpdate
from app.core.security import hash_secret
from app.schemas.member import MemberCreate, MemberResponse, MemberUpdate

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OrganizationResponse:
    if current_user.organization_id != org_id and current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        
    return OrganizationResponse(
        id=org.id, name=org.name, slug=org.slug, 
        timezone=org.timezone, status=org.status, created_at=org.created_at
    )

@router.get("/{org_id}/members", response_model=list[MemberResponse], dependencies=[Depends(RoleChecker(["ADMIN", "MANAGER"]))])
async def list_members(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[MemberResponse]:
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    res = await db.execute(select(User).where(User.organization_id == org_id))
    users = res.scalars().all()
    
    return [
        MemberResponse(
            id=u.id, email=u.email, first_name=u.first_name,
            last_name=u.last_name, role=u.role, is_active=u.is_active, created_at=u.created_at
        ) for u in users
    ]

@router.post("/{org_id}/members", status_code=status.HTTP_201_CREATED, response_model=MemberResponse, dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def add_member(
    org_id: uuid.UUID,
    payload: MemberCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MemberResponse:
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    new_user = User(
        id=uuid.uuid4(), organization_id=org_id, email=payload.email,
        password_hash=hash_secret(payload.password), first_name=payload.first_name,
        last_name=payload.last_name, role=payload.role
    )
    db.add(new_user)
    await db.commit()
    
    return MemberResponse(
        id=new_user.id, email=new_user.email, first_name=new_user.first_name,
        last_name=new_user.last_name, role=new_user.role, is_active=new_user.is_active, created_at=new_user.created_at
    )

@router.patch("/{org_id}/members/{member_id}", response_model=MemberResponse, dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def update_member_role(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MemberResponse:
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    res = await db.execute(select(User).where(User.id == member_id, User.organization_id == org_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        
    user.role = payload.role
    await db.commit()
    
    return MemberResponse(
        id=user.id, email=user.email, first_name=user.first_name,
        last_name=user.last_name, role=user.role, is_active=user.is_active, created_at=user.created_at
    )

@router.delete("/{org_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def remove_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if current_user.id == member_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
        
    res = await db.execute(select(User).where(User.id == member_id, User.organization_id == org_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        
    # Soft delete
    user.is_active = False
    await db.commit()