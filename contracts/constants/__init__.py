"""Dependency-free constants shared by Python services."""

from .permissions import APPROVE, DELETE, MANAGE, SUBMIT, VIEW
from .roles import COORDINATOR, OWNER, VIEWER

__all__ = [
    "APPROVE",
    "COORDINATOR",
    "DELETE",
    "MANAGE",
    "OWNER",
    "SUBMIT",
    "VIEW",
    "VIEWER",
]
