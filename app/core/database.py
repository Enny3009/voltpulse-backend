from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import logger

# Path A: SQLAlchemy 2.0 Async Engine for Relational Entities
async_engine: AsyncEngine = create_async_engine(
    settings.ASYNC_DATABASE_URI,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development",
)

AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding isolated async ORM sessions."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Path B: Raw asyncpg Connection Pool for High-Throughput Bulk Operations
class RawDatabasePool:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        if self.pool is None:
            logger.info("initializing_raw_asyncpg_pool")
            self.pool = await asyncpg.create_pool(
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                min_size=5,
                max_size=settings.DATABASE_POOL_SIZE,
                command_timeout=60,
            )

    async def close(self) -> None:
        if self.pool:
            logger.info("closing_raw_asyncpg_pool")
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        if self.pool is None:
            raise RuntimeError("RawDatabasePool is not initialized.")
        async with self.pool.acquire() as connection:
            yield connection


raw_db_pool = RawDatabasePool()