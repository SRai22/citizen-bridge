import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
user_id: ContextVar[str] = ContextVar("user_id", default="")

_STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}


def _is_sensitive(field: str) -> bool:
    name = field.lower()
    return any(
        part in name for part in ("password", "secret", "api_key", "authorization")
    ) or name.endswith("token")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": getattr(record, "service", record.name),
            "correlation_id": correlation_id.get(),
            "user_id": user_id.get(),
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_FIELDS
                and key not in payload
                and not key.startswith("_")
            ):
                payload[key] = "[redacted]" if _is_sensitive(key) else value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


class ContextLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    def process(
        self, msg: object, kwargs: dict[str, Any]
    ) -> tuple[object, dict[str, Any]]:
        kwargs["extra"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


def configure_logging(service_name: str) -> ContextLoggerAdapter:
    formatter = JsonFormatter()
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for logger in (
        root,
        *(
            logging.getLogger(name)
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
        ),
    ):
        for handler in logger.handlers:
            handler.setFormatter(formatter)
    root.setLevel(logging.INFO)
    return ContextLoggerAdapter(
        logging.getLogger(service_name), {"service": service_name}
    )


def set_correlation_id(value: str) -> Token[str]:
    return correlation_id.set(value)


def reset_correlation_id(token: Token[str]) -> None:
    correlation_id.reset(token)


def set_user_id(value: str) -> Token[str]:
    return user_id.set(value)


def reset_user_id(token: Token[str]) -> None:
    user_id.reset(token)
