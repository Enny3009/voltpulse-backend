from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "voltpulse_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "check-device-connectivity-every-minute": {
            "task": "app.workers.scheduled_tasks.check_device_connectivity",
            "schedule": 60.0,
        },
        "rollup-hourly-energy": {
            "task": "app.workers.scheduled_tasks.rollup_hourly_energy",
            "schedule": crontab(minute=5),  # 5 minutes past every hour
        },
        "purge-expired-raw-telemetry-daily": {
            "task": "app.workers.scheduled_tasks.purge_expired_raw_telemetry",
            "schedule": crontab(hour=2, minute=0),  # 02:00 UTC daily
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])