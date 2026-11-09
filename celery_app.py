from celery import Celery

celery = Celery(
    "trek_app",
    broker="redis://localhost:6379/1",      # where tasks wait in a queue
    backend="redis://localhost:6379/2",     # where results are stored
    include=["tasks"],
)
celery.conf.timezone = "Asia/Kolkata"