import os

from celery import Celery
from celery.schedules import crontab
from flask import current_app

# Celery configuration with Redis
celery = Celery(
    "helpchain",
    broker=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
    backend=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
    include=["tasks"],
)

# Enhanced Celery configuration
celery.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Sofia",
    enable_utc=True,
    # Result backend settings
    result_expires=3600,
    result_cache_max=10000,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    # Task routing
    task_routes={
        "tasks.send_notification": {"queue": "notifications"},
        "tasks.send_email_with_retry": {"queue": "emails"},
        "tasks.retry_failed_emails": {"queue": "emails"},
        "tasks.requeue_dlq_emails": {"queue": "emails"},
        "tasks.auto_match_requests": {"queue": "matching"},
        "tasks.generate_daily_reports": {"queue": "reports"},
        "tasks.process_ml_analysis": {"queue": "ml"},
        "tasks.update_realtime_stats": {"queue": "stats"},
    },
    # Task time limits
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    # Beat scheduler settings
    beat_schedule={
        # "send-reminders": {
        #     "task": "tasks.send_reminders",
        #     "schedule": crontab(hour="9,14,19"),  # 3 times a day
        # },
        "auto-match-requests": {
            "task": "tasks.auto_match_requests",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
        "generate-daily-reports": {
            "task": "tasks.generate_daily_reports",
            "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
        },
        "cleanup-old-data": {
            "task": "tasks.cleanup_old_data",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Weekly on Sunday
        },
        "monitor-system-health": {
            "task": "tasks.monitor_system_health",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
        "update-realtime-stats": {
            "task": "tasks.update_realtime_stats",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "retry-failed-emails": {
            "task": "tasks.retry_failed_emails",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
        "requeue-dlq-emails": {
            "task": "tasks.requeue_dlq_emails",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "args": (100,),  # до 100 съобщения на цикъл
        },
    },
)


class ContextTask(celery.Task):
    """Make celery tasks work with Flask app context."""

    def __call__(self, *args, **kwargs):
        with current_app.app_context():
            return self.run(*args, **kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failures"""
        current_app.logger.error(f"Task {task_id} failed: {exc}")
        # Could send notifications or store failure metrics
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        current_app.logger.info(f"Task {task_id} completed successfully")
        super().on_success(retval, task_id, args, kwargs)


celery.Task = ContextTask
