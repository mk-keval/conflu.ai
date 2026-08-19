"""Celery application for conflu.ai background tasks."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

from backend.app.core.config import settings

# Celery app
celery_app = Celery("conflu")

# Broker configuration
celery_app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app.conf.broker_transport = "redis"
# Use RPC result backend for better Windows compatibility
celery_app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "rpc://")

# Serialization
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Timezone
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# Task routing
celery_app.conf.task_routes = {
    "backend.app.worker.tasks.ingest_asset_class": {"queue": "ingestion"},
    "backend.app.worker.tasks.ingest_all": {"queue": "ingestion"},
    "backend.app.worker.tasks.health_check": {"queue": "ingestion"},
    "backend.app.worker.tasks.periodic_daily_ingestion": {"queue": "ingestion"},
    "backend.app.worker.tasks.periodic_intraday_ingestion": {"queue": "ingestion"},
}

# Worker settings
celery_app.conf.worker_prefetch_multiplier = 4
celery_app.conf.worker_max_tasks_per_child = 100
celery_app.conf.task_acks_late = True

# Beat schedule - configured dynamically from settings
celery_app.conf.beat_schedule = {}


def configure_beat_schedule() -> None:
    """Configure periodic tasks from settings."""
    ingestion = settings.ingestion

    # Daily full ingestion at configured UTC time
    hour, minute = map(int, ingestion.daily_schedule_utc.split(":"))
    celery_app.conf.beat_schedule["daily-full-ingestion"] = {
        "task": "backend.app.worker.tasks.ingest_all",
        "schedule": crontab(hour=hour, minute=minute),
        "options": {"queue": "ingestion"},
    }

    # Intraday ingestion every N seconds (converted to minutes for crontab)
    # For sub-minute intervals, we'd use a different approach
    interval_minutes = max(1, ingestion.intraday_interval_s // 60)
    if interval_minutes < 60:
        # Every N minutes — use periodic_intraday_ingestion which filters out
        # 1D bars so we don't re-fetch daily history every cycle (bug B9).
        celery_app.conf.beat_schedule["intraday-ingestion"] = {
            "task": "backend.app.worker.tasks.periodic_intraday_ingestion",
            "schedule": crontab(minute=f"*/{interval_minutes}"),
            "options": {"queue": "ingestion"},
        }
    else:
        # Hourly
        celery_app.conf.beat_schedule["hourly-ingestion"] = {
            "task": "backend.app.worker.tasks.periodic_intraday_ingestion",
            "schedule": crontab(minute=0),
            "options": {"queue": "ingestion"},
        }


# Auto-configure on import
configure_beat_schedule()

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "backend.app.worker.tasks",
])


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing."""
    print(f"Request: {self.request!r}")
