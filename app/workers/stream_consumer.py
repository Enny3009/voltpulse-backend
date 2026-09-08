import asyncio
from datetime import datetime, timezone
import json
import signal
import uuid
import asyncpg
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.database import raw_db_pool
from app.core.logging import logger, setup_logging
from app.core.redis import CG_DB_PERSISTER, STREAM_TELEMETRY_RAW, get_redis_client

CONSUMER_NAME = f"worker-persister-{uuid.uuid4().hex[:8]}"
SHUTDOWN_EVENT = asyncio.Event()


def handle_exit_signals():
    SHUTDOWN_EVENT.set()
    logger.info("shutdown_signal_received", consumer=CONSUMER_NAME)


def parse_float_or_none(val: str | None) -> float | None:
    return float(val) if val and val.strip() else None


def parse_int_or_none(val: str | None) -> int | None:
    return int(val) if val and val.strip() else None


async def persist_batch_to_postgres(
    conn: asyncpg.Connection,
    records: list[tuple],
) -> None:
    """
    Streams records into PostgreSQL using binary bulk copy protocol.
    Bypasses standard INSERT and ORM overhead entirely.
    """
    columns = [
        "recorded_at",
        "id",
        "device_id",
        "voltage",
        "current",
        "power_kw",
        "energy_kwh",
        "temperature",
        "pressure",
        "frequency",
        "power_factor",
        "runtime_seconds",
        "metadata",
        "created_at",
    ]
    await conn.copy_records_to_table(
        "telemetry_readings",
        records=records,
        columns=columns,
    )


async def process_stream_entries(
    redis: aioredis.Redis,
    messages: list[tuple[str, dict]],
) -> None:
    if not messages:
        return

    records_to_copy = []
    message_ids = []
    now_utc = datetime.now(timezone.utc)

    for msg_id, payload in messages:
        try:
            record = (
                datetime.fromisoformat(payload["recorded_at"]),
                uuid.UUID(payload["id"]),
                uuid.UUID(payload["device_id"]),
                parse_float_or_none(payload.get("voltage")),
                parse_float_or_none(payload.get("current")),
                parse_float_or_none(payload.get("power_kw")),
                parse_float_or_none(payload.get("energy_kwh")),
                parse_float_or_none(payload.get("temperature")),
                parse_float_or_none(payload.get("pressure")),
                parse_float_or_none(payload.get("frequency")),
                parse_float_or_none(payload.get("power_factor")),
                parse_int_or_none(payload.get("runtime_seconds")),
                payload.get("metadata", "{}"),
                now_utc,
            )
            records_to_copy.append(record)
            message_ids.append(msg_id)
        except Exception as parse_err:
            logger.error("payload_parsing_failed", error=str(parse_err), msg_id=msg_id)
            # Acknowledge unparseable messages to prevent PEL poisoning
            await redis.xack(STREAM_TELEMETRY_RAW, CG_DB_PERSISTER, msg_id)

    if records_to_copy:
        async with raw_db_pool.acquire() as conn:
            async with conn.transaction():
                await persist_batch_to_postgres(conn, records_to_copy)

        # Acknowledge messages after successful DB transaction
        await redis.xack(STREAM_TELEMETRY_RAW, CG_DB_PERSISTER, *message_ids)
        logger.info(
            "telemetry_batch_persisted",
            count=len(records_to_copy),
            consumer=CONSUMER_NAME,
        )


async def run_consumer_loop() -> None:
    setup_logging()
    logger.info("starting_stream_persister_worker", consumer=CONSUMER_NAME)
    await raw_db_pool.initialize()
    redis = await get_redis_client()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_exit_signals)

    last_claim_check = 0.0

    while not SHUTDOWN_EVENT.is_set():
        try:
            current_time = loop.time()

            # 1. Recovery Check: Reclaim orphaned messages every 15s (min idle: 30s)
            if current_time - last_claim_check > 15.0:
                last_claim_check = current_time
                claim_result = await redis.xautoclaim(
                    name=STREAM_TELEMETRY_RAW,
                    groupname=CG_DB_PERSISTER,
                    consumername=CONSUMER_NAME,
                    min_idle_time=30000,
                    start_id="0-0",
                    count=settings.INGEST_BATCH_SIZE,
                )
                claimed_messages = claim_result[1]
                if claimed_messages:
                    logger.warn("reclaimed_stale_pel_messages", count=len(claimed_messages))
                    await process_stream_entries(redis, claimed_messages)

            # 2. Main Stream Ingestion via XREADGROUP
            response = await redis.xreadgroup(
                groupname=CG_DB_PERSISTER,
                consumername=CONSUMER_NAME,
                streams={STREAM_TELEMETRY_RAW: ">"},
                count=settings.INGEST_BATCH_SIZE,
                block=settings.INGEST_BATCH_TIMEOUT_MS,
            )

            if response:
                for _, messages in response:
                    await process_stream_entries(redis, messages)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("consumer_worker_error", error=str(exc))
            await asyncio.sleep(1.0)

    logger.info("shutting_down_persister_worker", consumer=CONSUMER_NAME)
    await redis.aclose()
    await raw_db_pool.close()


if __name__ == "__main__":
    asyncio.run(run_consumer_loop())