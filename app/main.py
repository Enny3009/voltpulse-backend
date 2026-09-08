from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import raw_db_pool
from app.core.logging import logger, setup_logging
from app.core.redis import close_redis_pool, get_redis_client, setup_redis_streams
from app.websocket.endpoints import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("starting_voltpulse_engine", environment=settings.ENVIRONMENT)
    
    # Initialize asyncpg raw pool and Redis stream consumer groups
    await raw_db_pool.initialize()
    redis_client = await get_redis_client()
    await setup_redis_streams(redis_client)
    await redis_client.close()

    yield

    # Shutdown
    logger.info("shutting_down_voltpulse_engine")
    await raw_db_pool.close()
    await close_redis_pool()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "HEALTHY", "service": settings.APP_NAME}