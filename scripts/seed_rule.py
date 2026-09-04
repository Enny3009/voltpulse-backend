# scripts/seed_rule.py
import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionFactory
from app.models.alert import AlertRule
from app.models.device import Device
from app.models.site import Site


async def seed_rule():
    async with AsyncSessionFactory() as session:
        # Eager load the device's site relationship
        query = (
            select(Device)
            .options(selectinload(Device.site))
            .where(Device.device_code == "GEN-001")
        )
        res = await session.execute(query)
        device = res.scalar_one_or_none()

        if not device:
            print("Device GEN-001 not found.")
            return

        rule = AlertRule(
            organization_id=device.site.organization_id,
            site_id=device.site_id,
            device_id=device.id,
            name="Generator Overheating Critical",
            metric="temperature",
            condition="GT",
            threshold=85.0,
            severity="CRITICAL",
        )
        session.add(rule)
        await session.commit()
        print("--- ALERT RULE SEEDED ---")
        print(f"Rule: Temperature > 85.0 C for GEN-001")
        print(f"Site ID (use this for WebSocket subscription): {device.site_id}")


if __name__ == "__main__":
    asyncio.run(seed_rule())