from celery import Celery

celery = Celery(
    "pronester",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)
