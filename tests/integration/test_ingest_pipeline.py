import pytest
from httpx import AsyncClient
from app.core.redis import STREAM_TELEMETRY_RAW, get_redis_client

@pytest.mark.asyncio
async def test_telemetry_ingestion_writes_to_redis(async_client: AsyncClient):
    payload = {
        "voltage": 415.2,
        "current": 128.4,
        "power_kw": 89.6,
        "temperature": 74.2
    }
    
    # We use the seeded test credentials
    headers = {
        "X-Device-Code": "GEN-001",
        "X-Device-Key": "sec_live_voltpulse_test_key"
    }
    
    response = await async_client.post("/api/v1/telemetry", json=payload, headers=headers)
    
    # Verify API accepted the request
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert "event_id" in data
    
    # Verify the payload was buffered into the Redis Stream
    redis = await get_redis_client()
    stream_data = await redis.xrevrange(STREAM_TELEMETRY_RAW, max="+", min="-", count=1)
    
    assert len(stream_data) == 1
    msg_id, msg_dict = stream_data[0]
    
    assert float(msg_dict["power_kw"]) == 89.6
    assert float(msg_dict["temperature"]) == 74.2
    
    await redis.aclose()