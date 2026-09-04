import math
import random
import time
from simulator.devices.base import BaseDeviceSimulator


class DieselGeneratorSimulator(BaseDeviceSimulator):
    def __init__(self, api_url: str, device_code: str, device_key: str, sampling_interval: float = 5.0):
        super().__init__(api_url, device_code, device_key, sampling_interval)
        self.base_temperature = 72.0
        self.temperature = self.base_temperature
        self.total_runtime_seconds = 120000

    def generate_telemetry(self) -> dict:
        self.total_runtime_seconds += int(self.sampling_interval)
        t = time.time()

        # Normal industrial fluctuation
        daily_cycle = 0.5 + 0.5 * math.sin(t / 3600.0)
        power_kw = round(40.0 + (50.0 * daily_cycle) + random.uniform(-2.0, 2.0), 2)
        voltage = round(415.0 + random.uniform(-1.5, 1.5), 1)
        current = round((power_kw * 1000) / (math.sqrt(3) * voltage * 0.95), 1)
        frequency = round(50.0 + random.uniform(-0.05, 0.05), 2)
        power_factor = round(0.92 + random.uniform(-0.02, 0.02), 2)

        # Fault: Thermal Runaway (simulates coolant pump failure)
        if self.fault_active == "thermal_runaway":
            self.temperature += random.uniform(3.0, 6.0)
        else:
            # Gradual return to equilibrium
            target_temp = self.base_temperature + (power_kw * 0.15)
            self.temperature += (target_temp - self.temperature) * 0.1 + random.uniform(-0.2, 0.2)

        return {
            "voltage": voltage,
            "current": current,
            "power_kw": power_kw,
            "energy_kwh": round(self.total_runtime_seconds * (power_kw / 3600.0), 2),
            "temperature": round(self.temperature, 2),
            "pressure": round(4.2 + random.uniform(-0.1, 0.1), 2),  # Bar
            "frequency": frequency,
            "power_factor": power_factor,
            "runtime_seconds": self.total_runtime_seconds,
            "metadata": {"load_state": "HEAVY" if power_kw > 70 else "NOMINAL"},
        }