from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class TelemetryPayload(BaseModel):
    """Single telemetry frame from an edge device."""
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO timestamp when the measurement was taken at the edge",
    )
    voltage: float | None = Field(default=None, ge=0.0, le=500000.0)
    current: float | None = Field(default=None, ge=0.0, le=50000.0)
    power_kw: float | None = Field(default=None, ge=0.0, le=1000000.0)
    energy_kwh: float | None = Field(default=None, ge=0.0)
    temperature: float | None = Field(default=None, ge=-50.0, le=500.0)
    pressure: float | None = Field(default=None, ge=0.0, le=1000.0)
    frequency: float | None = Field(default=None, ge=0.0, le=100.0)
    power_factor: float | None = Field(default=None, ge=-1.0, le=1.0)
    runtime_seconds: int | None = Field(default=None, ge=0)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class TelemetryBatchPayload(BaseModel):
    """Micro-batch array of telemetry frames (up to 500 items)."""
    readings: list[TelemetryPayload] = Field(..., min_length=1, max_length=500)


class TelemetryIngestResponse(BaseModel):
    status: str = "ACCEPTED"
    event_id: str | None = None
    batch_count: int = 1
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))