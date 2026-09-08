from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, Double, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin


class Anomaly(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "anomalies"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Double, nullable=False)
    expected_value: Mapped[float] = mapped_column(Double, nullable=False)
    deviation_score: Mapped[float] = mapped_column(Double, nullable=False)  # Z-score value
    algorithm: Mapped[str] = mapped_column(String(64), default="Z_SCORE", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="FLAGGED", nullable=False)