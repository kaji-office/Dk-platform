FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN pip install --no-cache-dir build installer

COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["celery", "-A", "workflow_worker.celery_app", "worker", "--loglevel=info"]
