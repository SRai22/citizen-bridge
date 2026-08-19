"""Adapter factory for configured government service integrations."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import GovernmentAdapter
from app.adapters.bescom import BescomTransferAdapter
from app.adapters.death_certificate import DeathCertificateAdapter

AdapterFactory = Callable[[AsyncSession], GovernmentAdapter]

ADAPTER_REGISTRY: dict[str, AdapterFactory] = {
    "bescom": BescomTransferAdapter,
    "death_certificate": DeathCertificateAdapter,
}


class UnknownAdapterError(LookupError):
    """Raised when no adapter is registered for a workflow adapter type."""


def get_adapter(adapter_type: str, session: AsyncSession) -> GovernmentAdapter:
    """Create the registered adapter using the caller's database session."""
    try:
        factory = ADAPTER_REGISTRY[adapter_type]
    except KeyError as error:
        raise UnknownAdapterError(f"Unknown government adapter: {adapter_type}") from error
    return factory(session)
