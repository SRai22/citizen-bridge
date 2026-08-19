"""Government service adapter contracts and implementations."""

from app.adapters.base import (
    AdapterResult,
    AdapterStatus,
    GovernmentAdapter,
    StatusResult,
    SubmissionResult,
)
from app.adapters.death_certificate import DeathCertificateAdapter
from app.adapters.registry import ADAPTER_REGISTRY, UnknownAdapterError, get_adapter

__all__ = [
    "ADAPTER_REGISTRY",
    "AdapterResult",
    "AdapterStatus",
    "DeathCertificateAdapter",
    "GovernmentAdapter",
    "StatusResult",
    "SubmissionResult",
    "UnknownAdapterError",
    "get_adapter",
]
