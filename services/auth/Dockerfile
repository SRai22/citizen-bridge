# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app
WORKDIR /app/services/auth

COPY services/auth/pyproject.toml ./
COPY services/auth/alembic.ini ./
COPY services/auth/alembic ./alembic
COPY services/auth/app ./app
COPY contracts /app/contracts
RUN pip install --no-cache-dir .

RUN addgroup --system app && adduser --system --ingroup app app
USER app

EXPOSE 8001 50051
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"$HTTP_PORT\""]
