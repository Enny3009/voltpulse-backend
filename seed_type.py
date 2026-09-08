import asyncio
import uuid
from app.core.database import AsyncSessionFactory
from app.models.device import DeviceType

async def seed():
    async with AsyncSessionFactory() as session:
        dtype = DeviceType(
            id=uuid.UUID("6d2a6927-d336-443b-bd53-1da2f9bb4447"),
            name="TURBINE",
            manufacturer="General Electric",
            model="GE-9HA",
            metric_definitions={"voltage": "V", "power_kw": "kW", "temperature": "C"}
        )
        session.add(dtype)
        await session.commit()
        print("Device Type seeded successfully.")

asyncio.run(seed())