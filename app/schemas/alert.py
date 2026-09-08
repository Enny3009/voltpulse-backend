from datetime import datetime
import uuid
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    metric: str
    actual_value: float
    threshold: float
    severity: str
    status: str
    message: str
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class AlertActionResponse(BaseModel):
    alert_id: uuid.UUID
    status: str
    updated_at: datetime