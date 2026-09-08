from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class DeviceCreateRequest(BaseModel):
    site_id: uuid.UUID
    device_type_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=255)
    device_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    sampling_rate_seconds: int = Field(default=5, ge=1, le=3600)


class DeviceProvisionResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    device_code: str
    device_key: str  # Displayed once upon creation
    created_at: datetime


class DeviceStatusResponse(BaseModel):
    device_id: uuid.UUID
    status: str
    health_score: int
    current_power_kw: float
    current_temperature: float | None
    is_online: bool
    last_telemetry_at: datetime | None


class HistoricalTelemetryPoint(BaseModel):
    recorded_at: datetime
    power_kw: float | None
    voltage: float | None
    current: float | None
    temperature: float | None
    frequency: float | None