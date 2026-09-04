import asyncio
import json
from fastapi import WebSocket
import redis.asyncio as aioredis
from starlette.websockets import WebSocketState
from app.core.logging import logger
from app.core.redis import get_redis_client


class WebSocketConnectionManager:
    def __init__(self):
        self.active_subscriptions: dict[str, set[WebSocket]] = {}
        self.pubsub_task: asyncio.Task | None = None
        self.redis_pubsub: aioredis.client.PubSub | None = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channels: list[str] | str):
        # Only accept once
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()

        if isinstance(channels, str):
            channels = [channels]

        async with self._lock:
            for channel in channels:
                if channel not in self.active_subscriptions:
                    self.active_subscriptions[channel] = set()
                self.active_subscriptions[channel].add(websocket)
                logger.info(
                    "websocket_client_subscribed",
                    channel=channel,
                    total=len(self.active_subscriptions[channel]),
                )

            if self.pubsub_task is None or self.pubsub_task.done():
                self.pubsub_task = asyncio.create_task(self._pubsub_listener())

    async def disconnect(self, websocket: WebSocket, channels: list[str] | str):
        if isinstance(channels, str):
            channels = [channels]

        async with self._lock:
            for channel in channels:
                if channel in self.active_subscriptions:
                    self.active_subscriptions[channel].discard(websocket)
                    if not self.active_subscriptions[channel]:
                        del self.active_subscriptions[channel]
            logger.info("websocket_client_unsubscribed", channels=channels)

    async def _broadcast_to_subscribers(self, channel: str, message: str):
        async with self._lock:
            subscribers = self.active_subscriptions.get(channel, set()).copy()

        for ws in subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(ws, channel)

    async def _pubsub_listener(self):
        logger.info("starting_redis_pubsub_bridge_listener")
        redis = await get_redis_client()
        pubsub = redis.pubsub()
        self.redis_pubsub = pubsub

        await pubsub.psubscribe("ch:site:*")

        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    data = message["data"]
                    await self._broadcast_to_subscribers(channel, data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("redis_pubsub_listener_error", error=str(e))
        finally:
            await pubsub.aclose()
            await redis.aclose()


ws_manager = WebSocketConnectionManager()