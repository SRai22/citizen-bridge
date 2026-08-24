# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app
WORKDIR /app/services/service-template

COPY services/service-template/pyproject.toml ./
COPY services/service-template/alembic.ini ./
COPY services/service-template/alembic ./alembic
COPY services/service-template/app ./app
COPY contracts /app/contracts
RUN pip install --no-cache-dir .

RUN addgroup --system app && adduser --system --ingroup app app
USER app

EXPOSE 8000 50051
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:' + os.getenv('HTTP_PORT', '8000') + '/health')"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$HTTP_PORT\""]
