from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import (
    CyclicDependencyError,
    DependencySolver,
    InvalidDependencyError,
    TaskNotFoundError,
)
from app.db.session import create_database_engine, init_db
from app.models import Case, Task, TaskDependency, TaskStatus


@pytest.fixture
async def solver_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, DependencySolver]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'solver.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        yield session, DependencySolver(session)
    await engine.dispose()


async def create_tasks(
    session: AsyncSession,
    statuses: list[TaskStatus],
) -> list[Task]:
    case = Case()
    tasks = [
        Task(
            case=case,
            workflow_id=f"workflow_{index}",
            task_type=f"task_{index}",
            status=status,
            title=f"Task {index}",
        )
        for index, status in enumerate(statuses)
    ]
    session.add(case)
    await session.flush()
    return tasks


def edge(task: Task, prerequisite: Task) -> TaskDependency:
    return TaskDependency(task_id=task.id, depends_on_task_id=prerequisite.id)


@pytest.mark.anyio
async def test_linear_chain_readiness(
    solver_context: tuple[AsyncSession, DependencySolver],
) -> None:
    session, solver = solver_context
    task_a, task_b, task_c = await create_tasks(
        session,
        [TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.PENDING],
    )
    session.add_all([edge(task_b, task_a), edge(task_c, task_b)])
    await session.flush()

    changes = await solver.evaluate_readiness(task_a.case_id)

    assert changes == {task_b.id: TaskStatus.READY}
    assert task_b.status == TaskStatus.PENDING


@pytest.mark.anyio
async def test_fan_out_readiness(solver_context: tuple[AsyncSession, DependencySolver]) -> None:
    session, solver = solver_context
    task_a, task_b, task_c, task_d = await create_tasks(
        session,
        [TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.PENDING],
    )
    session.add_all([edge(task_b, task_a), edge(task_c, task_a), edge(task_d, task_a)])
    await session.flush()

    assert await solver.evaluate_readiness(task_a.case_id) == {
        task_b.id: TaskStatus.READY,
        task_c.id: TaskStatus.READY,
        task_d.id: TaskStatus.READY,
    }


@pytest.mark.anyio
async def test_fan_in_requires_every_prerequisite(
    solver_context: tuple[AsyncSession, DependencySolver],
) -> None:
    session, solver = solver_context
    task_b, task_c, task_d = await create_tasks(
        session,
        [TaskStatus.COMPLETED, TaskStatus.READY, TaskStatus.PENDING],
    )
    session.add_all([edge(task_d, task_b), edge(task_d, task_c)])
    await session.flush()

    assert await solver.evaluate_readiness(task_d.case_id) == {}
    task_c.status = TaskStatus.COMPLETED
    await session.flush()
    assert await solver.evaluate_readiness(task_d.case_id) == {task_d.id: TaskStatus.READY}


@pytest.mark.anyio
async def test_dynamic_dependency_blocks_then_unblocks_ready_task(
    solver_context: tuple[AsyncSession, DependencySolver],
) -> None:
    session, solver = solver_context
    task_d, task_e = await create_tasks(session, [TaskStatus.READY, TaskStatus.READY])

    await solver.add_dependency(task_d.id, task_e.id)
    assert await solver.evaluate_readiness(task_d.case_id) == {task_d.id: TaskStatus.BLOCKED}

    task_d.status = TaskStatus.BLOCKED
    task_e.status = TaskStatus.COMPLETED
    await session.flush()
    assert await solver.evaluate_readiness(task_d.case_id) == {task_d.id: TaskStatus.READY}


@pytest.mark.anyio
async def test_dependency_validation_and_cycle_detection(
    solver_context: tuple[AsyncSession, DependencySolver],
) -> None:
    session, solver = solver_context
    task_a, task_b = await create_tasks(session, [TaskStatus.READY, TaskStatus.PENDING])
    other_case_task = (await create_tasks(session, [TaskStatus.PENDING]))[0]

    with pytest.raises(InvalidDependencyError, match="itself"):
        await solver.add_dependency(task_a.id, task_a.id)
    with pytest.raises(TaskNotFoundError):
        await solver.add_dependency(task_a.id, uuid4())
    with pytest.raises(InvalidDependencyError, match="same case"):
        await solver.add_dependency(task_a.id, other_case_task.id)

    dependency = await solver.add_dependency(task_b.id, task_a.id)
    assert await solver.add_dependency(task_b.id, task_a.id) is dependency
    with pytest.raises(CyclicDependencyError):
        await solver.add_dependency(task_a.id, task_b.id)


@pytest.mark.anyio
async def test_graph_is_json_serializable_and_uses_prerequisite_direction(
    solver_context: tuple[AsyncSession, DependencySolver],
) -> None:
    session, solver = solver_context
    upstream, downstream = await create_tasks(
        session,
        [TaskStatus.COMPLETED, TaskStatus.READY],
    )
    await solver.add_dependency(downstream.id, upstream.id)

    graph = await solver.get_dependency_graph(upstream.case_id)

    assert graph["nodes"] == [
        {"id": str(upstream.id), "label": "Task 0", "status": "completed"},
        {"id": str(downstream.id), "label": "Task 1", "status": "ready"},
    ]
    assert graph["edges"] == [{"source": str(upstream.id), "target": str(downstream.id)}]
    assert all(isinstance(UUID(node["id"]), UUID) for node in graph["nodes"])
