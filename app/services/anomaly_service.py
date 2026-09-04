import math
import numpy as np
import redis.asyncio as aioredis
from app.core.logging import logger

WINDOW_SIZE = 100
Z_SCORE_THRESHOLD = 3.0  # 99.7% confidence deviation


class AnomalyEvaluator:
    @staticmethod
    async def record_and_evaluate(
        redis: aioredis.Redis,
        device_id: str,
        metric: str,
        value: float,
        timestamp_ms: float,
    ) -> tuple[bool, float, float, float]:
        """
        Maintains sliding window of last 100 observations in Redis.
        Returns: (is_anomaly, z_score, mean, std_dev)
        """
        key = f"zset:device:{device_id}:{metric}"

        # Atomic transaction: Add current observation and trim window to last 100
        pipe = redis.pipeline(transaction=True)
        pipe.zadd(key, {f"{value}:{timestamp_ms}": timestamp_ms})
        pipe.zremrangebyrank(key, 0, -(WINDOW_SIZE + 1))
        pipe.zrange(key, 0, -1)
        pipe.expire(key, 86400)  # 24h retention
        results = await pipe.execute()

        raw_elements = results[2]
        if len(raw_elements) < 10:
            # Insufficient samples to establish a stable statistical baseline
            return False, 0.0, value, 0.0

        # Extract values into NumPy array for vectorized calculation
        values = np.array([float(elem.split(":")[0]) for elem in raw_elements], dtype=np.float64)

        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))

        if std < 1e-6:
            # Zero or near-zero variance
            return False, 0.0, mean, 0.0

        z_score = (value - mean) / std
        is_anomaly = abs(z_score) > Z_SCORE_THRESHOLD

        if is_anomaly:
            logger.warn(
                "statistical_anomaly_detected",
                device_id=device_id,
                metric=metric,
                value=value,
                mean=round(mean, 2),
                z_score=round(z_score, 2),
            )

        return is_anomaly, z_score, mean, std