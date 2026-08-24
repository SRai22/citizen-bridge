from time import perf_counter

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
GRPC_REQUESTS = Counter("grpc_requests_total", "gRPC requests", ["method", "status"])
GRPC_DURATION = Histogram(
    "grpc_request_duration_seconds", "gRPC request duration", ["method"]
)
KAFKA_PUBLISHED = Counter(
    "kafka_events_published_total", "Kafka events published", ["topic", "event_type"]
)
KAFKA_CONSUMED = Counter(
    "kafka_events_consumed_total", "Kafka events consumed", ["topic", "event_type"]
)
KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag", "Kafka consumer lag", ["topic", "partition"]
)
ACTIVE_CASES = Gauge("active_cases_total", "Active cases")
TASKS_BY_STATUS = Gauge("tasks_by_status", "Tasks by status", ["status"])


async def http_metrics_middleware(request: Request, call_next) -> Response:
    started = perf_counter()
    response = await call_next(request)
    path = getattr(request.scope.get("route"), "path", request.url.path)
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    HTTP_DURATION.labels(request.method, path).observe(perf_counter() - started)
    return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
