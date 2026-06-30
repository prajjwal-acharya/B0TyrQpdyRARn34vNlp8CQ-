import os

from celery import Celery

_broker = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "pipeline",
    broker=_broker,
    backend=_broker,
    # Auto-import task modules when the worker starts
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Route all pipeline.* tasks to the "pipeline" queue
    task_routes={"pipeline.*": {"queue": "pipeline"}},
    task_default_queue="pipeline",
    # Reliability: ack only after successful task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Prevent prefetch pile-up so tasks retry promptly
    worker_prefetch_multiplier=1,
)
