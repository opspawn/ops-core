"""
Unit tests for the InMemoryMetadataStore.
"""

import pytest
import uuid

from ops_core.models import Task, TaskStatus
from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError


@pytest.fixture
def store() -> InMemoryMetadataStore:
    """Provides a fresh InMemoryMetadataStore instance for each test."""
    return InMemoryMetadataStore()


@pytest.fixture
def sample_task() -> Task:
    """Provides a sample Task object."""
    return Task(
        task_id=f"task_{uuid.uuid4()}", # Use correct field name and add prefix
        name="Test Task",
        task_type="test",
        status=TaskStatus.PENDING,
        input_data={"param": "value"},
    )


@pytest.mark.asyncio
async def test_add_task_success(store: InMemoryMetadataStore, sample_task: Task):
    """Tests successfully adding a new task."""
    await store.add_task(sample_task)
    retrieved_task = await store.get_task(sample_task.task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == sample_task.task_id
    assert retrieved_task.name == sample_task.name
    # Ensure it's a copy
    assert retrieved_task is not sample_task


@pytest.mark.asyncio
async def test_add_task_duplicate_id(store: InMemoryMetadataStore, sample_task: Task):
    """Tests adding a task with an existing ID raises ValueError."""
    await store.add_task(sample_task)
    with pytest.raises(ValueError, match=f"Task with ID '{sample_task.task_id}' already exists."):
        await store.add_task(sample_task)


@pytest.mark.asyncio
async def test_get_task_found(store: InMemoryMetadataStore, sample_task: Task):
    """Tests retrieving an existing task."""
    await store.add_task(sample_task)
    retrieved_task = await store.get_task(sample_task.task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == sample_task.task_id
    # Ensure it's a copy
    assert retrieved_task is not sample_task
    assert retrieved_task.input_data == sample_task.input_data


@pytest.mark.asyncio
async def test_get_task_not_found(store: InMemoryMetadataStore):
    """Tests retrieving a non-existent task returns None."""
    retrieved_task = await store.get_task("non-existent-id")
    assert retrieved_task is None


@pytest.mark.asyncio
async def test_update_task_status_success(store: InMemoryMetadataStore, sample_task: Task):
    """Tests successfully updating a task's status."""
    await store.add_task(sample_task)
    updated_task = await store.update_task_status(sample_task.task_id, TaskStatus.RUNNING)

    assert updated_task is not None
    assert updated_task.task_id == sample_task.task_id
    assert updated_task.status == TaskStatus.RUNNING

    # Verify the change in the store
    retrieved_task = await store.get_task(sample_task.task_id)
    assert retrieved_task is not None
    assert retrieved_task.status == TaskStatus.RUNNING
    # Ensure it's a copy
    assert updated_task is not retrieved_task


@pytest.mark.asyncio
async def test_update_task_status_not_found(store: InMemoryMetadataStore):
    """Tests updating a non-existent task raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError, match="Task with ID 'non-existent-id' not found."):
        await store.update_task_status("non-existent-id", TaskStatus.COMPLETED)


@pytest.mark.asyncio
async def test_list_tasks_empty(store: InMemoryMetadataStore):
    """Tests listing tasks when the store is empty."""
    tasks = await store.list_tasks()
    assert tasks == []


@pytest.mark.asyncio
async def test_list_tasks_all(store: InMemoryMetadataStore, sample_task: Task):
    """Tests listing all tasks."""
    # Use model_copy and correct field name
    task2 = sample_task.model_copy(update={"task_id": f"task_{uuid.uuid4()}", "status": TaskStatus.RUNNING})
    await store.add_task(sample_task)
    await store.add_task(task2)

    tasks = await store.list_tasks()
    assert len(tasks) == 2
    task_ids = {t.task_id for t in tasks} # Use task_id
    assert sample_task.task_id in task_ids
    assert task2.task_id in task_ids
    # Ensure they are copies
    assert tasks[0] is not sample_task
    assert tasks[1] is not task2


@pytest.mark.asyncio
async def test_list_tasks_with_filter(store: InMemoryMetadataStore, sample_task: Task):
    """Tests listing tasks with a status filter."""
    task_pending = sample_task
    # Use model_copy and correct field name
    task_running = sample_task.model_copy(update={"task_id": f"task_{uuid.uuid4()}", "status": TaskStatus.RUNNING})
    task_completed = sample_task.model_copy(update={"task_id": f"task_{uuid.uuid4()}", "status": TaskStatus.COMPLETED})

    await store.add_task(task_pending)
    await store.add_task(task_running)
    await store.add_task(task_completed)

    # Filter PENDING
    pending_tasks = await store.list_tasks(status_filter=TaskStatus.PENDING)
    assert len(pending_tasks) == 1
    assert pending_tasks[0].task_id == task_pending.task_id # Use task_id
    assert pending_tasks[0].status == TaskStatus.PENDING
    # Ensure it's a copy
    assert pending_tasks[0] is not task_pending


    # Filter RUNNING
    running_tasks = await store.list_tasks(status_filter=TaskStatus.RUNNING)
    assert len(running_tasks) == 1
    assert running_tasks[0].task_id == task_running.task_id # Use task_id
    assert running_tasks[0].status == TaskStatus.RUNNING

    # Filter COMPLETED
    completed_tasks = await store.list_tasks(status_filter=TaskStatus.COMPLETED)
    assert len(completed_tasks) == 1
    assert completed_tasks[0].task_id == task_completed.task_id # Use task_id
    assert completed_tasks[0].status == TaskStatus.COMPLETED

    # Filter FAILED (should be empty)
    failed_tasks = await store.list_tasks(status_filter=TaskStatus.FAILED)
    assert failed_tasks == []


@pytest.mark.asyncio
async def test_delete_task_success(store: InMemoryMetadataStore, sample_task: Task):
    """Tests successfully deleting a task."""
    await store.add_task(sample_task)
    assert await store.get_task(sample_task.task_id) is not None # Use task_id

    deleted = await store.delete_task(sample_task.task_id) # Use task_id
    assert deleted is True
    assert await store.get_task(sample_task.task_id) is None # Use task_id


@pytest.mark.asyncio
async def test_delete_task_not_found(store: InMemoryMetadataStore):
    """Tests deleting a non-existent task returns False."""
    deleted = await store.delete_task("non-existent-id")
    assert deleted is False
