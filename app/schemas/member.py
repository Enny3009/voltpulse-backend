from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, Field

class MemberCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern="^(ADMIN|MANAGER|OPERATOR|VIEWER)$")

class MemberUpdate(BaseModel):
    role: str = Field(..., pattern="^(ADMIN|MANAGER|OPERATOR|VIEWER)$")

class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: datetime