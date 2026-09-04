from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import random
import httpx


class BaseDeviceSimulator(ABC):
    def __init__(self, api_url: str, device_code: str, device_key: str, sampling_interval: float = 5.0):
        self.api_url = api_url
        self.device_code = device_code
        self.device_key = device_key
        self.sampling_interval = sampling_interval
        self.is_running = False
        self.fault_active: str | None = None

    @abstractmethod
    def generate_telemetry(self) -> dict:
        """Subclasses generate physical sensor signals according to their equipment profile."""
        pass

    def inject_fault(self, fault_type: str):
        self.fault_active = fault_type

    def clear_fault(self):
        self.fault_active = None

    async def run(self, client: httpx.AsyncClient):
        self.is_running = True
        endpoint = f"{self.api_url}/api/v1/telemetry"
        headers = {
            "X-Device-Code": self.device_code,
            "X-Device-Key": self.device_key,
            "Content-Type": "application/json",
        }

        while self.is_running:
            payload = self.generate_telemetry()
            payload["recorded_at"] = datetime.now(timezone.utc).isoformat()

            try:
                resp = await client.post(endpoint, json=payload, headers=headers, timeout=2.0)
                if resp.status_code != 202:
                    print(f"[{self.device_code}] Ingestion Rejected: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"[{self.device_code}] Network transmission failure: {e}")

            await asyncio.sleep(self.sampling_interval)