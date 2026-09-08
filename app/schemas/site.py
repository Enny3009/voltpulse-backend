from datetime import datetime
import uuid
from pydantic import BaseModel, Field

class SiteCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    address: str | None = None
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str = "UTC"

class SiteResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    is_active: bool
    created_at: datetime