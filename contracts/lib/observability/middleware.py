import re
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from .logging import reset_correlation_id, set_correlation_id

_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _correlation_id(value: str | None) -> str:
    return value if value and _VALID_CORRELATION_ID.fullmatch(value) else str(uuid4())


async def correlation_middleware(request: Request, call_next) -> Response:
    value = _correlation_id(request.headers.get("X-Correlation-ID"))
    token = set_correlation_id(value)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = value
        return response
    finally:
        reset_correlation_id(token)


def grpc_metadata() -> tuple[tuple[str, str], ...]:
    from .logging import correlation_id

    return (("x-correlation-id", correlation_id.get()),)


def kafka_headers() -> list[tuple[str, bytes]]:
    from .logging import correlation_id

    return [("x-correlation-id", correlation_id.get().encode())]
