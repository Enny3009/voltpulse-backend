from datetime import datetime
import uuid
from sqlalchemy import DateTime, Double, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TelemetryReading(Base):
    """
    Master declarative model for telemetry_readings.
    Must be created using PostgreSQL PARTITION BY RANGE (recorded_at).
    """
    __tablename__ = "telemetry_readings"
    __table_args__ = (
        PrimaryKeyConstraint("recorded_at", "id", name="pk_telemetry_readings"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    voltage: Mapped[float | None] = mapped_column(Double, nullable=True)
    current: Mapped[float | None] = mapped_column(Double, nullable=True)
    power_kw: Mapped[float | None] = mapped_column(Double, nullable=True)
    energy_kwh: Mapped[float | None] = mapped_column(Double, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Double, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Double, nullable=True)
    frequency: Mapped[float | None] = mapped_column(Double, nullable=True)
    power_factor: Mapped[float | None] = mapped_column(Double, nullable=True)
    runtime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)