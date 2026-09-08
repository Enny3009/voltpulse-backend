from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.connection_manager import ws_manager

router = APIRouter(prefix="/ws/v1", tags=["Real-Time WebSockets"])


@router.websocket("/sites/{site_id}")
async def site_telemetry_stream(websocket: WebSocket, site_id: str):
    channels = [
        f"ch:site:{site_id}:telemetry",
        f"ch:site:{site_id}:alerts",
    ]

    await ws_manager.connect(websocket, channels)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channels)