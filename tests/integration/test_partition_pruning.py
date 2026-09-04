import json
import pytest
from sqlalchemy import text
from app.core.database import AsyncSessionFactory


@pytest.mark.asyncio
async def test_postgresql_partition_pruning():
    """
    Verifies that PostgreSQL's query planner executes partition pruning
    by scanning ONLY the partition matching the recorded_at filter.
    """
    async with AsyncSessionFactory() as session:
        # Query targeting a single month
        query = text("""
            EXPLAIN (FORMAT JSON)
            SELECT * FROM telemetry_readings
            WHERE recorded_at >= '2026-09-01 00:00:00+00' 
              AND recorded_at < '2026-10-01 00:00:00+00';
        """)
        res = await session.execute(query)
        plan_json = res.scalar()
        plan_str = json.dumps(plan_json)

        # Confirm September partition was targeted
        assert "telemetry_readings_y2026_m09" in plan_str, "September partition must be scanned"
        # Confirm partitions for unqueried months were pruned out
        assert "telemetry_readings_y2026_m01" not in plan_str, "Unrelated partitions must be pruned"