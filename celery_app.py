import os
import sys

from celery import Celery

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

celery = Celery(
    "trek_app",
    broker="redis://localhost:6379/1",      # where tasks wait in a queue
    backend="redis://localhost:6379/2",     # where results are stored
    include=["tasks"],
)
celery.conf.timezone = "Asia/Kolkata"

from celery.schedules import crontab

celery.conf.beat_schedule = {
    "daily-reminders": {
        "task": "tasks.send_daily_reminders",
        "schedule": crontab(hour=8, minute=0),                    # every day at 8:00 AM
    },
    "monthly-report": {
        "task": "tasks.generate_monthly_report",
        "schedule": crontab(day_of_month=1, hour=9, minute=0),    # 1st of every month, 9:00 AM
    },
}