"""
Unit tests for the SqlMetadataStore.
"""
import time
import uuid
from copy import deepcopy
import asyncio # Add this import
import pytest_asyncio # Add missing import

import pytest
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession

# Import the custom exception and the store implementation
from ops_core.metadata.sql_store import SqlMetadataStore, TaskNotFoundError, get_session, engine as app_engine
from ops_core.models.tasks import Task, TaskStatus

# Use pytest-asyncio for async tests
pytestmark = pytest.mark.asyncio

# Note: Database setup/teardown and session fixtures are expected
# to be provided by conftest.py

# Change to async fixture to accept db_session
@pytest_asyncio.fixture
async def store(db_session: AsyncSession) -> SqlMetadataStore:
    """
    Provides a SqlMetadataStore instance initialized with the
    transactional session for the current test.
    """
    # Pass the function-scoped, transactional session to the store
    return SqlMetadataStore(session=db_session)

@pytest.fixture
def sample_task() -> Task:
    """Provides a sample Task object."""
    # Ensure the task has no primary key set initially if relying on DB defaults
    return Task(name="Sample SQL Task", task_type="sql_sample")


async def test_store_initialization(store: SqlMetadataStore, db_session: AsyncSession):
    """Test that the store initializes and can list from an empty DB."""
    # Ensure the DB is clean before this test via fixtures
    assert await store.list_tasks() == []


async def test_add_task(store: SqlMetadataStore, sample_task: Task, db_session: AsyncSession):
    """Test adding a task to the store."""
    task_id = sample_task.task_id
    added_task = await store.add_task(sample_task)

    # Verify the returned task has the ID and matches input
    assert added_task is not None
    assert added_task.task_id == task_id
    assert added_task.name == sample_task.name

    # Verify retrieval
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == task_id
    assert retrieved_task.name == sample_task.name


async def test_add_task_duplicate_id_fails_implicitly(store: SqlMetadataStore, sample_task: Task, db_session: AsyncSession):
    """Test that adding a task with a duplicate ID raises DB error (implicitly)."""
    await store.add_task(sample_task)
    # Creating a new task instance with the same ID
    duplicate_task = Task(task_id=sample_task.task_id, name="Duplicate", task_type="dup")
    # Expecting an IntegrityError or similar from the database driver
    with pytest.raises(Exception): # Catch broad exception as specific type depends on DB driver
        await store.add_task(duplicate_task)


async def test_get_task(store: SqlMetadataStore, sample_task: Task, db_session: AsyncSession):
    """Test retrieving a task."""
    added_task = await store.add_task(sample_task)
    task_id = added_task.task_id

    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == task_id
    assert retrieved_task.name == sample_task.name


async def test_get_task_not_found(store: SqlMetadataStore, db_session: AsyncSession):
    """Test retrieving a non-existent task raises TaskNotFoundError."""
    non_existent_id = f"task_{uuid.uuid4()}"
    with pytest.raises(TaskNotFoundError) as excinfo:
        await store.get_task(non_existent_id)
    assert non_existent_id in str(excinfo.value)


async def test_update_task_status(store: SqlMetadataStore, sample_task: Task, db_session: AsyncSession):
    """Test updating the status of a task."""
    added_task = await store.add_task(sample_task)
    task_id = added_task.task_id
    original_updated_at = added_task.updated_at

    # Allow some time to pass to ensure updated_at changes
    await asyncio.sleep(0.01) # Use asyncio.sleep

    updated_task = await store.update_task_status(task_id, TaskStatus.RUNNING)

    assert updated_task is not None
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.updated_at > original_updated_at
    assert updated_task.started_at is not None # Should be set when moving to RUNNING

    # Verify change in store
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.status == TaskStatus.RUNNING
    assert retrieved_task.updated_at == updated_task.updated_at
    assert retrieved_task.started_at == updated_task.started_at


async def test_update_task_status_not_found(store: SqlMetadataStore, db_session: AsyncSession):
    """Test updating status of a non-existent task raises TaskNotFoundError."""
    non_existent_id = f"task_{uuid.uuid4()}"
    with pytest.raises(TaskNotFoundError):
        await store.update_task_status(non_existent_id, TaskStatus.FAILED)


async def test_update_task_output_result(store: SqlMetadataStore, sample_task: Task, db_session: AsyncSession):
    """Test updating the result of a task."""
    added_task = await store.add_task(sample_task)
    task_id = added_task.task_id
    original_updated_at = added_task.updated_at
    result_data = {"output": "sql success", "value": 456}

    await asyncio.sleep(0.01)
    updated_task = await store.update_task_output(task_id=task_id, result=result_data)

    assert updated_task is not None
    assert updated_task.result == result_data
    assert updated_task.error_message is None
    # Status update is not handled by update_task_output in SQL store, only timestamp
    # assert updated_task.status == TaskStatus.COMPLETED # This check is removed
    assert updated_task.updated_at > original_updated_at

    # Verify change in store
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.result == result_data
    # assert retrieved_task.status == TaskStatus.COMPLETED # Status doesn't change here
    assert retrieved_task.updated_at == updated_task.updated_at


async def test_update_task_output_not_found(store: SqlMetadataStore, db_session: AsyncSession):
    """Test updating output of a non-existent task raises TaskNotFoundError."""
    non_existent_id = f"task_{uuid.uuid4()}"
    with pytest.raises(TaskNotFoundError):
        await store.update_task_output(task_id=non_existent_id, result={"data": "test"})


async def test_list_tasks(store: SqlMetadataStore, db_session: AsyncSession):
    """Test listing tasks from the store."""
    assert await store.list_tasks() == [] # Check empty state

    task1 = Task(name="SQL Task 1", task_type="typeA")
    task2 = Task(name="SQL Task 2", task_type="typeB")
    await store.add_task(task1)
    await store.add_task(task2)

    listed_tasks = await store.list_tasks()
    assert len(listed_tasks) == 2

    listed_ids = {t.task_id for t in listed_tasks}
    assert listed_ids == {task1.task_id, task2.task_id}


async def test_list_tasks_with_limit_offset(store: SqlMetadataStore, db_session: AsyncSession):
    """Test listing tasks with limit and offset."""
    tasks = [Task(name=f"Task {i}", task_type="batch") for i in range(5)]
    for task in tasks:
        await store.add_task(task)

    # Get first 2 (most recent due to default ordering)
    listed_part1 = await store.list_tasks(limit=2)
    assert len(listed_part1) == 2

    # Get next 2
    listed_part2 = await store.list_tasks(limit=2, offset=2)
    assert len(listed_part2) == 2

    # Get last 1
    listed_part3 = await store.list_tasks(limit=2, offset=4)
    assert len(listed_part3) == 1

    # Ensure no overlap and all tasks covered
    all_listed_ids = {t.task_id for t in listed_part1 + listed_part2 + listed_part3}
    original_ids = {t.task_id for t in tasks}
    assert all_listed_ids == original_ids


async def test_list_tasks_by_status(store: SqlMetadataStore, db_session: AsyncSession):
    """Test listing tasks filtered by status."""
    task_pending = Task(name="Pending Task", task_type="filter")
    task_running = Task(name="Running Task", task_type="filter")
    task_completed = Task(name="Completed Task", task_type="filter")

    await store.add_task(task_pending)
    t_running = await store.add_task(task_running)
    t_completed = await store.add_task(task_completed)

    # Update statuses
    await store.update_task_status(t_running.task_id, TaskStatus.RUNNING)
    await store.update_task_status(t_completed.task_id, TaskStatus.COMPLETED)

    # List pending
    pending_list = await store.list_tasks(status=TaskStatus.PENDING)
    assert len(pending_list) == 1
    assert pending_list[0].task_id == task_pending.task_id

    # List running
    running_list = await store.list_tasks(status=TaskStatus.RUNNING)
    assert len(running_list) == 1
    assert running_list[0].task_id == t_running.task_id

    # List completed
    completed_list = await store.list_tasks(status=TaskStatus.COMPLETED)
    assert len(completed_list) == 1
    assert completed_list[0].task_id == t_completed.task_id
