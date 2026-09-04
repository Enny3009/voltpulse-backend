from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.site import Site


class DeviceType(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "device_types"

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # GENERATOR, TRANSFORMER, etc.
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_definitions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    devices: Mapped[list["Device"]] = relationship(back_populates="device_type")


class Device(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("site_id", "device_code", name="uq_device_site_code"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("device_types.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_code: Mapped[str] = mapped_column(String(64), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    installation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="OFFLINE", nullable=False)
    sampling_rate_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    site: Mapped["Site"] = relationship(back_populates="devices")
    device_type: Mapped["DeviceType"] = relationship(back_populates="devices")
    credential: Mapped["DeviceCredential"] = relationship(
        back_populates="device", uselist=False, cascade="all, delete-orphan"
    )
    operational_status: Mapped["DeviceStatus"] = relationship(
        back_populates="device", uselist=False, cascade="all, delete-orphan"
    )


class DeviceCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "device_credentials"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    credential_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="credential")


class DeviceStatus(Base):
    """Real-time operational cache in PostgreSQL, updated by the background stream worker."""
    __tablename__ = "device_status"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    current_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    device: Mapped["Device"] = relationship(back_populates="operational_status")