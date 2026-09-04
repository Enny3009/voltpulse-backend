"""create partitioned telemetry schema

Revision ID: 002_partitioned_telemetry
Revises: 001_initial_metadata
Create Date: 2026-09-02 20:00:00.000000
"""
from datetime import datetime, timezone
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_partitioned_telemetry"
down_revision: Union[str, None] = "001_initial_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the Master Partitioned Hyper-Table
    op.execute("""
        CREATE TABLE telemetry_readings (
            recorded_at TIMESTAMPTZ NOT NULL,
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            voltage DOUBLE PRECISION,
            current DOUBLE PRECISION,
            power_kw DOUBLE PRECISION,
            energy_kwh DOUBLE PRECISION,
            temperature DOUBLE PRECISION,
            pressure DOUBLE PRECISION,
            frequency DOUBLE PRECISION,
            power_factor DOUBLE PRECISION,
            runtime_seconds INTEGER,
            metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            PRIMARY KEY (recorded_at, id)
        ) PARTITION BY RANGE (recorded_at);
    """)

    # 2. Performance Indexes
    op.execute("""
        CREATE INDEX idx_telemetry_device_time 
        ON telemetry_readings (device_id, recorded_at DESC);
    """)
    op.execute("""
        CREATE INDEX idx_telemetry_brin_time 
        ON telemetry_readings USING BRIN (recorded_at);
    """)

    # 3. Dynamic Partition Generation (Previous month, Current month, Next 6 months)
    now = datetime.now(timezone.utc)
    for offset in range(-1, 7):
        year = now.year + (now.month + offset - 1) // 12
        month = (now.month + offset - 1) % 12 + 1

        next_year = year + (1 if month == 12 else 0)
        next_month = 1 if month == 12 else month + 1

        p_start = f"{year}-{month:02d}-01 00:00:00+00"
        p_end = f"{next_year}-{next_month:02d}-01 00:00:00+00"
        partition_name = f"telemetry_readings_y{year}_m{month:02d}"

        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {partition_name} 
            PARTITION OF telemetry_readings
            FOR VALUES FROM ('{p_start}') TO ('{p_end}');
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telemetry_readings CASCADE;")