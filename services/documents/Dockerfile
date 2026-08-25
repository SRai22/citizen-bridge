# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONPATH=/app
WORKDIR /app/services/documents
COPY services/documents/pyproject.toml services/documents/alembic.ini ./
COPY services/documents/alembic ./alembic
COPY services/documents/app ./app
COPY contracts /app/contracts
RUN pip install --no-cache-dir .
RUN addgroup --system app && adduser --system --ingroup app app
USER app
EXPOSE 8004 50054
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"$HTTP_PORT\""]
