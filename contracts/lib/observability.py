"""Dependency-free structured logging and correlation context."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "correlation_id": correlation_id.get(),
            },
            separators=(",", ":"),
        )


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def set_correlation_id(value: str) -> Token[str]:
    return correlation_id.set(value)


def reset_correlation_id(token: Token[str]) -> None:
    correlation_id.reset(token)
