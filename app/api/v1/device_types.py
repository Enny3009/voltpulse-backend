import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db_session
from app.models.device import DeviceType
from app.models.user import User
from app.schemas.device_type import DeviceTypeCreate, DeviceTypeResponse

router = APIRouter(prefix="/device-types", tags=["Device Types"])

@router.post("", status_code=status.HTTP_201_CREATED, response_model=DeviceTypeResponse, dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def create_device_type(
    payload: DeviceTypeCreate,
    db: AsyncSession = Depends(get_db_session),
) -> DeviceTypeResponse:
    dtype = DeviceType(
        id=uuid.uuid4(),
        name=payload.name,
        manufacturer=payload.manufacturer,
        model=payload.model,
        metric_definitions=payload.metric_definitions
    )
    db.add(dtype)
    await db.commit()
    return DeviceTypeResponse(
        id=dtype.id, name=dtype.name, manufacturer=dtype.manufacturer,
        model=dtype.model, metric_definitions=dtype.metric_definitions
    )

@router.get("", response_model=list[DeviceTypeResponse])
async def list_device_types(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[DeviceTypeResponse]:
    query = select(DeviceType).limit(limit).offset(offset)
    res = await db.execute(query)
    dtypes = res.scalars().all()
    return [
        DeviceTypeResponse(
            id=d.id, name=d.name, manufacturer=d.manufacturer,
            model=d.model, metric_definitions=d.metric_definitions
        ) for d in dtypes
    ]