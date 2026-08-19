"""Repository abstractions for database access."""

from app.repositories.cases import CaseRepository
from app.repositories.tasks import TaskRepository

__all__ = ["CaseRepository", "TaskRepository"]
