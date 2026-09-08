from datetime import datetime
import uuid
from pydantic import BaseModel

class EnergyAggregateResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    interval: str
    energy_consumed_kwh: float
    average_power_kw: float
    peak_power_kw: float
    minimum_power_kw: float