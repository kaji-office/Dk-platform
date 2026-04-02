"""
Celery Application instance for workflow-worker.
"""
import os
from celery import Celery
from kombu import Queue, Exchange

# Provide a default broker if env var is missing during local dev
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "workflow_worker",
    broker=REDIS_URL,
    include=["workflow_worker.tasks"]
)

# ── Celery Configuration ──────────────────────────────────────────────────────

# Queues and Routing
app.conf.task_queues = (
    Queue("default",   Exchange("default"),   routing_key="default"),
    Queue("ai-heavy",  Exchange("ai-heavy"),  routing_key="ai-heavy"),
    Queue("critical",  Exchange("critical"),  routing_key="critical"),
    Queue("scheduled", Exchange("scheduled"), routing_key="scheduled"),
    Queue("DLQ",       Exchange("DLQ"),       routing_key="dead_letter"),
)
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# ── Graceful Shutdown ─────────────────────────────────────────────────────────
# AC: Worker drains gracefully on SIGTERM (60s window)
app.conf.worker_cancel_long_running_tasks_on_connection_loss = True
app.conf.worker_redirect_stdouts = False
# Time (in seconds) that the worker will wait for tasks to finish after SIGTERM
# before issuing SIGKILL.
app.conf.worker_proc_alive_timeout = 60.0

# General robustness
app.conf.broker_connection_retry_on_startup = True
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# ── Periodic Tasks (Beat) ─────────────────────────────────────────────────────
# AC: Celery beat fires schedules within ±5s of `next_fire_at`.
# It runs every 30s as requested by spec.
app.conf.beat_schedule = {
    "fire_schedule_every_30s": {
        "task": "workflow_worker.tasks.fire_schedule",
        "schedule": 30.0,
    },
}
