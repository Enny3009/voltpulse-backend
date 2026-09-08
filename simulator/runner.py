import argparse
import asyncio
import httpx
from simulator.devices.generator import DieselGeneratorSimulator


async def main():
    parser = argparse.ArgumentParser(description="VoltPulse Industrial Edge Hardware Simulator")
    parser.add_argument("--api-url", default="http://localhost:8000", help="FastAPI target host")
    parser.add_argument("--device-code", default="GEN-001", help="Device Code to simulate")
    parser.add_argument("--device-key", default="sec_live_voltpulse_test_key", help="Pre-shared device key")
    parser.add_argument("--rate", type=float, default=2.0, help="Sampling interval in seconds")
    parser.add_argument("--inject-fault", choices=["thermal_runaway", "brownout"], default=None)
    parser.add_argument("--fault-delay", type=int, default=10, help="Seconds before injecting fault")
    args = parser.parse_args()

    device = DieselGeneratorSimulator(
        api_url=args.api_url,
        device_code=args.device_code,
        device_key=args.device_key,
        sampling_interval=args.rate,
    )

    print(f"[SIMULATOR] Initialized {args.device_code} at {args.api_url} (Sampling every {args.rate}s)")

    async with httpx.AsyncClient() as client:
        sim_task = asyncio.create_task(device.run(client))

        if args.inject_fault:
            print(f"[SIMULATOR] Scheduled fault '{args.inject_fault}' in {args.fault_delay} seconds...")
            await asyncio.sleep(args.fault_delay)
            device.inject_fault(args.inject_fault)
            print(f"!!! [SIMULATOR] FAULT INJECTED: {args.inject_fault} !!!")

        await sim_task


if __name__ == "__main__":
    asyncio.run(main())