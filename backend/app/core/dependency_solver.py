"""Deterministic task dependency validation and readiness evaluation."""

from graphlib import CycleError, TopologicalSorter
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, TaskDependency, TaskStatus


class DependencySolverError(ValueError):
    """Base class for invalid task dependency operations."""


class TaskNotFoundError(DependencySolverError):
    """Raised when a dependency references a task that does not exist."""


class InvalidDependencyError(DependencySolverError):
    """Raised when an edge violates a non-cyclic dependency invariant."""


class CyclicDependencyError(DependencySolverError):
    """Raised when a dependency would make the task graph cyclic."""


class DependencyGraphNode(TypedDict):
    id: str
    label: str
    status: str


class DependencyGraphEdge(TypedDict):
    source: str
    target: str


class DependencyGraph(TypedDict):
    nodes: list[DependencyGraphNode]
    edges: list[DependencyGraphEdge]


class DependencySolver:
    """Read and validate a case's dependency graph without changing task statuses.

    Dependency edges added here participate in the caller's transaction. The caller
    remains responsible for committing the edge and applying status changes returned
    by :meth:`evaluate_readiness`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate_readiness(self, case_id: UUID) -> dict[UUID, TaskStatus]:
        """Return proposed readiness changes for the mutable readiness states."""
        tasks = await self._tasks_for_case(case_id)
        prerequisites = await self._prerequisites_for_tasks(set(tasks))
        self._validate_acyclic(prerequisites)

        changes: dict[UUID, TaskStatus] = {}
        for task_id, task in tasks.items():
            dependencies_completed = all(
                tasks[dependency_id].status == TaskStatus.COMPLETED
                for dependency_id in prerequisites[task_id]
            )
            if dependencies_completed and task.status in {
                TaskStatus.PENDING,
                TaskStatus.BLOCKED,
            }:
                changes[task_id] = TaskStatus.READY
            elif not dependencies_completed and task.status == TaskStatus.READY:
                changes[task_id] = TaskStatus.BLOCKED

        return changes

    async def add_dependency(
        self,
        task_id: UUID,
        depends_on_task_id: UUID,
    ) -> TaskDependency:
        """Validate and stage a completion dependency in the current transaction."""
        if task_id == depends_on_task_id:
            raise InvalidDependencyError("A task cannot depend on itself")

        task = await self.session.get(Task, task_id)
        prerequisite = await self.session.get(Task, depends_on_task_id)
        missing_ids = [
            str(identifier)
            for identifier, candidate in (
                (task_id, task),
                (depends_on_task_id, prerequisite),
            )
            if candidate is None
        ]
        if missing_ids:
            raise TaskNotFoundError(f"Task not found: {', '.join(missing_ids)}")
        assert task is not None and prerequisite is not None

        if task.case_id != prerequisite.case_id:
            raise InvalidDependencyError("Both tasks in a dependency must belong to the same case")

        tasks = await self._tasks_for_case(task.case_id)
        prerequisites = await self._prerequisites_for_tasks(set(tasks))

        existing = await self.session.scalar(
            select(TaskDependency).where(
                TaskDependency.task_id == task_id,
                TaskDependency.depends_on_task_id == depends_on_task_id,
            )
        )
        if existing is not None:
            return existing

        prerequisites[task_id].add(depends_on_task_id)
        self._validate_acyclic(prerequisites)

        dependency = TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            dependency_type="completion",
        )
        self.session.add(dependency)
        await self.session.flush()
        return dependency

    async def get_dependency_graph(self, case_id: UUID) -> DependencyGraph:
        """Return a stable, JSON-serializable graph for frontend rendering."""
        tasks = await self._tasks_for_case(case_id)
        prerequisites = await self._prerequisites_for_tasks(set(tasks))
        self._validate_acyclic(prerequisites)

        ordered_tasks = sorted(tasks.values(), key=lambda task: (task.title, str(task.id)))
        nodes: list[DependencyGraphNode] = [
            {
                "id": str(task.id),
                "label": task.title,
                "status": task.status.value,
            }
            for task in ordered_tasks
        ]
        edges: list[DependencyGraphEdge] = [
            {"source": str(source), "target": str(target)}
            for target, sources in prerequisites.items()
            for source in sources
        ]
        edges.sort(key=lambda edge: (edge["source"], edge["target"]))
        return {"nodes": nodes, "edges": edges}

    async def _tasks_for_case(self, case_id: UUID) -> dict[UUID, Task]:
        result = await self.session.scalars(select(Task).where(Task.case_id == case_id))
        return {task.id: task for task in result.all()}

    async def _prerequisites_for_tasks(
        self,
        task_ids: set[UUID],
    ) -> dict[UUID, set[UUID]]:
        prerequisites: dict[UUID, set[UUID]] = {task_id: set() for task_id in task_ids}
        if not task_ids:
            return prerequisites

        result = await self.session.scalars(
            select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
        )
        for dependency in result.all():
            if dependency.depends_on_task_id not in task_ids:
                raise InvalidDependencyError(
                    "A dependency graph contains tasks from different cases"
                )
            prerequisites[dependency.task_id].add(dependency.depends_on_task_id)
        return prerequisites

    @staticmethod
    def _validate_acyclic(prerequisites: dict[UUID, set[UUID]]) -> None:
        try:
            TopologicalSorter(prerequisites).prepare()
        except CycleError as error:
            cycle = " -> ".join(str(task_id) for task_id in error.args[1])
            raise CyclicDependencyError(f"Dependency would create a cycle: {cycle}") from error
