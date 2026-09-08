import asyncio
from datetime import datetime, timezone
import json
import signal
import uuid
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.logging import logger, setup_logging
from app.core.redis import CG_RULES_EVALUATOR, STREAM_TELEMETRY_RAW, get_redis_client
from app.models.anomaly import Anomaly
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyEvaluator

CONSUMER_NAME = f"worker-anomaly-{uuid.uuid4().hex[:8]}"
SHUTDOWN_EVENT = asyncio.Event()


def handle_exit_signals():
    SHUTDOWN_EVENT.set()
    logger.info("shutdown_signal_received", consumer=CONSUMER_NAME)


async def process_evaluation_entries(redis: aioredis.Redis, messages: list[tuple[str, dict]]):
    for msg_id, payload in messages:
        try:
            device_id = payload["device_id"]
            site_id = payload["site_id"]
            recorded_at_dt = datetime.fromisoformat(payload["recorded_at"])
            timestamp_ms = recorded_at_dt.timestamp() * 1000

            # Extract numeric fields
            telemetry_data = {}
            for metric in ["voltage", "current", "power_kw", "temperature", "pressure", "frequency", "power_factor"]:
                val = payload.get(metric)
                if val and val.strip():
                    telemetry_data[metric] = float(val)

            # 1. Real-time broadcast: publish telemetry.tick frame to Redis Pub/Sub
            tick_payload = {
                "event": "telemetry.tick",
                "site_id": site_id,
                "device_id": device_id,
                "timestamp": payload["recorded_at"],
                "data": telemetry_data,
            }
            await redis.publish(f"ch:site:{site_id}:telemetry", json.dumps(tick_payload))

            # 2. Evaluate Z-Score statistical anomaly on power_kw and temperature
            for metric in ["power_kw", "temperature"]:
                if metric in telemetry_data:
                    val = telemetry_data[metric]
                    is_anomaly, z_score, mean, std = await AnomalyEvaluator.record_and_evaluate(
                        redis, device_id, metric, val, timestamp_ms
                    )
                    if is_anomaly:
                        # Persist anomaly record
                        async with AsyncSessionFactory() as session:
                            anomaly_record = Anomaly(
                                device_id=uuid.UUID(device_id),
                                metric=metric,
                                value=val,
                                expected_value=round(mean, 2),
                                deviation_score=round(z_score, 2),
                                severity="CRITICAL" if abs(z_score) > 4.0 else "WARNING",
                                status="FLAGGED",
                            )
                            session.add(anomaly_record)
                            await session.commit()

            # 3. Evaluate Rule-based Thresholds & Trigger Deduplicated Alerts
            await AlertService.process_reading_alerts(redis, site_id, device_id, telemetry_data)

            # Acknowledge message in Redis stream
            await redis.xack(STREAM_TELEMETRY_RAW, CG_RULES_EVALUATOR, msg_id)

        except Exception as exc:
            logger.error("anomaly_evaluation_failed", error=str(exc), msg_id=msg_id)
            await redis.xack(STREAM_TELEMETRY_RAW, CG_RULES_EVALUATOR, msg_id)


async def run_anomaly_loop():
    setup_logging()
    logger.info("starting_anomaly_evaluator_worker", consumer=CONSUMER_NAME)
    redis = await get_redis_client()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_exit_signals)

    while not SHUTDOWN_EVENT.is_set():
        try:
            response = await redis.xreadgroup(
                groupname=CG_RULES_EVALUATOR,
                consumername=CONSUMER_NAME,
                streams={STREAM_TELEMETRY_RAW: ">"},
                count=50,
                block=100,
            )
            if response:
                for _, messages in response:
                    await process_evaluation_entries(redis, messages)
        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error("anomaly_worker_error", error=str(err))
            await asyncio.sleep(1.0)

    logger.info("shutting_down_anomaly_worker", consumer=CONSUMER_NAME)
    await redis.close()


if __name__ == "__main__":
    asyncio.run(run_anomaly_loop())