from datetime import datetime
import uuid
from pydantic import BaseModel, Field

class AnomalyResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    metric: str
    value: float
    expected_value: float
    deviation_score: float
    algorithm: str
    severity: str
    detected_at: datetime
    status: str

class AnomalyUpdate(BaseModel):
    status: str = Field(..., pattern="^(FLAGGED|CONFIRMED|FALSE_POSITIVE)$")