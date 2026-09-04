# app/services/alert_service.py
from datetime import datetime, timezone
import json
import math
import uuid
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionFactory
from app.core.logging import logger
from app.models.alert import Alert, AlertRule


class AlertService:
    @staticmethod
    def evaluate_condition(actual: float, condition: str, threshold: float) -> bool:
        ops = {
            "GT": actual > threshold,
            "LT": actual < threshold,
            "GTE": actual >= threshold,
            "LTE": actual <= threshold,
            "EQUALS": math.isclose(actual, threshold, abs_tol=1e-5),
            "NOT_EQUALS": not math.isclose(actual, threshold, abs_tol=1e-5),
        }
        return ops.get(condition, False)

    @classmethod
    async def process_reading_alerts(
        cls,
        redis: aioredis.Redis,
        site_id: str,
        device_id: str,
        telemetry: dict[str, float],
    ) -> list[dict]:
        triggered_events = []

        rules_cache_key = f"cache:rules:{device_id}"
        cached_rules = await redis.get(rules_cache_key)

        if cached_rules:
            rules_data = json.loads(cached_rules)
        else:
            async with AsyncSessionFactory() as session:
                query = select(AlertRule).where(
                    AlertRule.is_enabled.is_(True),
                    (AlertRule.device_id == uuid.UUID(device_id))
                    | (AlertRule.site_id == uuid.UUID(site_id))
                    | (AlertRule.device_id.is_(None) & AlertRule.site_id.is_(None)),
                )
                res = await session.execute(query)
                rules = res.scalars().all()
                rules_data = [
                    {
                        "id": str(r.id),
                        "organization_id": str(r.organization_id),
                        "metric": r.metric,
                        "condition": r.condition,
                        "threshold": r.threshold,
                        "severity": r.severity,
                        "name": r.name,
                    }
                    for r in rules
                ]
                await redis.set(rules_cache_key, json.dumps(rules_data), ex=60)

        for rule in rules_data:
            metric_val = telemetry.get(rule["metric"])
            if metric_val is None:
                continue

            breached = cls.evaluate_condition(metric_val, rule["condition"], rule["threshold"])
            active_key = f"alert:active:{device_id}:{rule['id']}"
            active_alert_id = await redis.get(active_key)

            if breached and not active_alert_id:
                new_alert_id = uuid.uuid4()
                alert_msg = f"{rule['name']}: {rule['metric']} breached threshold ({metric_val} {rule['condition']} {rule['threshold']})"

                async with AsyncSessionFactory() as session:
                    alert_record = Alert(
                        id=new_alert_id,
                        organization_id=uuid.UUID(rule["organization_id"]),
                        device_id=uuid.UUID(device_id),
                        alert_rule_id=uuid.UUID(rule["id"]),
                        metric=rule["metric"],
                        actual_value=metric_val,
                        threshold=rule["threshold"],
                        severity=rule["severity"],
                        status="ACTIVE",
                        message=alert_msg,
                    )
                    session.add(alert_record)
                    await session.commit()

                await redis.set(active_key, str(new_alert_id), ex=86400)

                event_payload = {
                    "event": "alert.triggered",
                    "alert_id": str(new_alert_id),
                    "site_id": site_id,
                    "device_id": device_id,
                    "severity": rule["severity"],
                    "metric": rule["metric"],
                    "actual_value": metric_val,
                    "threshold": rule["threshold"],
                    "message": alert_msg,
                }
                await redis.publish(f"ch:site:{site_id}:alerts", json.dumps(event_payload))
                triggered_events.append(event_payload)

            elif not breached and active_alert_id:
                async with AsyncSessionFactory() as session:
                    query = select(Alert).where(Alert.id == uuid.UUID(active_alert_id))
                    res = await session.execute(query)
                    alert_record = res.scalar_one_or_none()
                    if alert_record and alert_record.status == "ACTIVE":
                        alert_record.status = "RESOLVED"
                        alert_record.resolved_at = datetime.now(timezone.utc)
                        await session.commit()

                await redis.delete(active_key)

                resolve_payload = {
                    "event": "alert.resolved",
                    "alert_id": active_alert_id,
                    "site_id": site_id,
                    "device_id": device_id,
                    "metric": rule["metric"],
                    "actual_value": metric_val,
                }
                await redis.publish(f"ch:site:{site_id}:alerts", json.dumps(resolve_payload))

        return triggered_events