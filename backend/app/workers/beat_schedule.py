from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    "purge-expired-soap-notes": {
        "task": "app.workers.maintenance_tasks.purge_expired_notes",
        "schedule": crontab(minute="*/15"),  # every 15 minutes
    },
    "purge-stale-audio-buffers": {
        "task": "app.workers.maintenance_tasks.purge_stale_audio",
        "schedule": crontab(minute="*/5"),  # every 5 minutes
    },
    "rotate-audit-archive": {
        "task": "app.workers.maintenance_tasks.archive_old_audit_logs",
        "schedule": crontab(hour=3, minute=0),  # daily at 03:00 UTC
    },
}
