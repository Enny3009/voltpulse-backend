from datetime import datetime
import uuid
from pydantic import BaseModel, Field

class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    status: str
    created_at: datetime

class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    timezone: str | None = Field(None, max_length=64)