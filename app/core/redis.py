import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import logger

redis_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    global redis_pool
    if redis_pool is None:
        logger.info("initializing_redis_connection_pool", host=settings.REDIS_HOST)
        redis_pool = aioredis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True,
        )
    return redis_pool


async def get_redis_client() -> aioredis.Redis:
    """Provides an async Redis client from the shared connection pool."""
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    global redis_pool
    if redis_pool:
        logger.info("closing_redis_connection_pool")
        await redis_pool.disconnect()
        redis_pool = None


# Stream Key Constants
STREAM_TELEMETRY_RAW = "stream:telemetry:raw"
CG_DB_PERSISTER = "cg:db:persister"
CG_RULES_EVALUATOR = "cg:rules:evaluator"


async def setup_redis_streams(client: aioredis.Redis) -> None:
    """
    Idempotently creates consumer groups for the telemetry stream.
    Creates the stream via MKSTREAM if it does not already exist.
    """
    consumer_groups = [CG_DB_PERSISTER, CG_RULES_EVALUATOR]
    for group in consumer_groups:
        try:
            await client.xgroup_create(
                name=STREAM_TELEMETRY_RAW,
                groupname=group,
                id="0",
                mkstream=True,
            )
            logger.info("redis_consumer_group_created", stream=STREAM_TELEMETRY_RAW, group=group)
        except aioredis.ResponseError as err:
            if "BUSYGROUP Consumer Group name already exists" in str(err):
                pass
            else:
                logger.error("redis_stream_group_init_failed", error=str(err))
                raise