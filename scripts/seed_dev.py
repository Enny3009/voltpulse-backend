# scripts/seed_dev.py
import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionFactory
from app.core.security import hash_secret
from app.models.device import Device, DeviceCredential, DeviceStatus, DeviceType
from app.models.organization import Organization
from app.models.site import Site


async def seed():
    async with AsyncSessionFactory() as session:
        # Organization
        org = Organization(
            name="VoltPulse Test Utilities",
            slug="voltpulse-test",
        )
        session.add(org)
        await session.flush()

        # Site
        site = Site(
            organization_id=org.id,
            code="FACILITY-LAGOS-01",
            name="Lagos Primary Microgrid Substation",
        )
        session.add(site)
        await session.flush()

        # Device Type
        dtype = DeviceType(
            name="GENERATOR",
            manufacturer="Caterpillar",
            model="CAT-C32",
            metric_definitions={"voltage": "V", "power_kw": "kW"},
        )
        session.add(dtype)
        await session.flush()

        # Device
        device = Device(
            site_id=site.id,
            device_type_id=dtype.id,
            name="Diesel Generator 01",
            device_code="GEN-001",
        )
        session.add(device)
        await session.flush()

        # Credential: raw key "sec_live_voltpulse_test_key"
        cred = DeviceCredential(
            device_id=device.id,
            credential_hash=hash_secret("sec_live_voltpulse_test_key"),
        )
        session.add(cred)

        # Operational Status
        status = DeviceStatus(device_id=device.id)
        session.add(status)

        await session.commit()
        print("--- SEEDING COMPLETE ---")
        print(f"Device Code: GEN-001")
        print(f"Device Key:  sec_live_voltpulse_test_key")


if __name__ == "__main__":
    asyncio.run(seed())