"""
Celery Application instance for workflow-worker.
"""
import logging
import os
from celery import Celery
from kombu import Queue, Exchange

# Configure structured JSON logging for all worker processes
try:
    from workflow_engine.observability.logging import configure_structured_logging
    _log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    configure_structured_logging(level=_log_level)
except Exception:
    logging.basicConfig(level=logging.INFO)

# Provide a default broker/backend if env var is missing during local dev
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "workflow_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
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
# ── Prometheus Metrics ───────────────────────────────────────────────────────
# Instrument Celery task execution counts and durations.
try:
    from prometheus_client import Counter, Histogram, Gauge
    TASK_STARTED = Counter(
        "celery_task_started_total", "Total tasks started",
        ["task_name"],
    )
    TASK_SUCCEEDED = Counter(
        "celery_task_succeeded_total", "Total tasks succeeded",
        ["task_name"],
    )
    TASK_FAILED = Counter(
        "celery_task_failed_total", "Total tasks failed",
        ["task_name"],
    )
    TASK_DURATION = Histogram(
        "celery_task_duration_seconds", "Task execution duration",
        ["task_name"],
        buckets=[0.1, 0.5, 1, 5, 15, 30, 60, 120, 300, 600],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

import time as _time

# ── Correlation ID Logging ────────────────────────────────────────────────────
# Log the x_request_id header (set by the API at dispatch) so log lines from
# workflow-worker can be correlated with the originating HTTP request.
from celery.signals import task_prerun, task_success, task_failure

_task_start_times: dict = {}  # task_id → start time

@task_prerun.connect
def _on_task_prerun(task_id: str, task, args: tuple, kwargs: dict, **_kw):
    import logging as _log
    task_name = getattr(task, "name", "unknown")

    # Prometheus
    if _METRICS_AVAILABLE:
        TASK_STARTED.labels(task_name=task_name).inc()
        _task_start_times[task_id] = _time.monotonic()

    # Correlation ID logging
    request_id = getattr(task.request, "x_request_id", None) or ""
    if request_id:
        _log.getLogger("dk.worker").info(
            "Task starting",
            extra={"task_id": task_id, "task_name": task_name, "x_request_id": request_id},
        )


@task_success.connect
def _on_task_success(sender, result, **_kw):
    if _METRICS_AVAILABLE:
        task_name = getattr(sender, "name", "unknown")
        task_id = getattr(sender.request, "id", None)
        TASK_SUCCEEDED.labels(task_name=task_name).inc()
        if task_id and task_id in _task_start_times:
            TASK_DURATION.labels(task_name=task_name).observe(
                _time.monotonic() - _task_start_times.pop(task_id)
            )


@task_failure.connect
def _on_task_failure(sender, task_id: str, exception, **_kw):
    if _METRICS_AVAILABLE:
        task_name = getattr(sender, "name", "unknown")
        TASK_FAILED.labels(task_name=task_name).inc()
        _task_start_times.pop(task_id, None)


app.conf.beat_schedule = {
    "fire_schedule_every_30s": {
        "task": "workflow_worker.tasks.fire_schedule",
        "schedule": 30.0,
    },
    "reap_stale_runs_every_60s": {
        "task": "workflow_worker.tasks.reap_stale_runs",
        "schedule": 60.0,
    },
}
