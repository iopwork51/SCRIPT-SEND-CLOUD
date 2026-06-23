from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "mailerpro",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.health_tasks", "app.tasks.send_tasks"],
)

celery_app.conf.beat_schedule = {
    "check-accounts-every-30min": {
        "task": "app.tasks.health_tasks.check_all_accounts",
        "schedule": 1800.0,
    },
    "reset-daily-sent-counters": {
        "task": "app.tasks.health_tasks.reset_daily_counters",
        "schedule": 86400.0,  # every 24h
    },
}
celery_app.conf.timezone = "UTC"
