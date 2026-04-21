"""
Celery application instance.
Broker and backend both use Redis.
"""
from celery import Celery
from config import get_settings

settings = get_settings()

celery_app = Celery(
    "clawbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "worker.tasks.run_supervisor_routing": {"queue": "default"},
        "worker.tasks.run_intake_workflow": {"queue": "default"},
        "worker.tasks.run_agent": {"queue": "agent_runs"},
    },
    task_soft_time_limit=300,   # 5 min soft limit
    task_time_limit=360,        # 6 min hard limit
)
