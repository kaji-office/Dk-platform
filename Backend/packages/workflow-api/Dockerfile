FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN pip install --no-cache-dir build installer

COPY pyproject.toml .
# Normally we'd copy poetry.lock or generate requirements, but pip install . works for a monorepo layer
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "workflow_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
