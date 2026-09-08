# scripts/ws_client.py
import asyncio
import sys
import websockets


async def listen(site_id: str):
    uri = f"ws://localhost:8000/ws/v1/sites/{site_id}"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected to WebSocket broadcast channel!")
        while True:
            msg = await ws.recv()
            print(f"\n[WS EVENT RECEIVED]:\n{msg}")


if __name__ == "__main__":
    site_id = sys.argv[1] if len(sys.argv) > 1 else "d47d0d05-5ac6-4d94-90db-f7903c3638e9"
    asyncio.run(listen(site_id))