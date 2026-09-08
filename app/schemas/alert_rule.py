from datetime import datetime
import uuid
from pydantic import BaseModel, Field

class AlertRuleCreate(BaseModel):
    site_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    name: str = Field(..., min_length=2, max_length=100)
    metric: str = Field(..., min_length=2, max_length=64)
    condition: str = Field(..., pattern="^(GT|LT|GTE|LTE|EQUALS|NOT_EQUALS)$")
    threshold: float
    severity: str = Field(..., pattern="^(INFO|WARNING|CRITICAL)$")
    duration_seconds: int = Field(default=0, ge=0)
    is_enabled: bool = True

class AlertRuleResponse(AlertRuleCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime