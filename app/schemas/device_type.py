import uuid
from pydantic import BaseModel, Field

class DeviceTypeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    manufacturer: str = Field(..., min_length=2, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    metric_definitions: dict = Field(default_factory=dict)

class DeviceTypeResponse(DeviceTypeCreate):
    id: uuid.UUID