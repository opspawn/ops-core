"""
Unit tests for the InMemoryMetadataStore.
"""
import time
import uuid
from copy import deepcopy

import pytest

# Import the custom exception
from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError
from ops_core.models.tasks import Task, TaskStatus


@pytest.fixture
def store() -> InMemoryMetadataStore:
    """Provides a fresh InMemoryMetadataStore for each test."""
    return InMemoryMetadataStore()


@pytest.fixture
def sample_task() -> Task:
    """Provides a sample Task object."""
    return Task(name="Sample Task", task_type="sample")


@pytest.mark.asyncio
async def test_store_initialization(store: InMemoryMetadataStore):
    """Test that the store initializes empty."""
    # Use public method instead of accessing private attribute
    assert await store.list_tasks() == []


@pytest.mark.asyncio
async def test_add_task(store: InMemoryMetadataStore, sample_task: Task):
    """Test adding a task to the store."""
    task_id = sample_task.task_id
    await store.add_task(sample_task)

    assert len(await store.list_tasks()) == 1
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == task_id
    assert retrieved_task.name == sample_task.name

    # Verify it stores a copy
    sample_task.name = "Modified Name"
    retrieved_task_after_modify = await store.get_task(task_id)
    assert retrieved_task_after_modify is not None
    assert retrieved_task_after_modify.name == "Sample Task"


@pytest.mark.asyncio
async def test_add_task_duplicate_id(store: InMemoryMetadataStore, sample_task: Task):
    """Test that adding a task with a duplicate ID raises ValueError."""
    await store.add_task(sample_task)
    with pytest.raises(ValueError) as excinfo:
        await store.add_task(sample_task) # Try adding the exact same task again
    # Match the exact error message format with single quotes around the ID
    assert f"Task with ID '{sample_task.task_id}' already exists." == str(excinfo.value)


@pytest.mark.asyncio
async def test_get_task(store: InMemoryMetadataStore, sample_task: Task):
    """Test retrieving a task."""
    await store.add_task(sample_task)
    task_id = sample_task.task_id

    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == task_id

    # Verify it returns a copy
    assert retrieved_task is not None # Needed for type checker
    retrieved_task.name = "Modified Retrieved"
    retrieved_task_again = await store.get_task(task_id)
    assert retrieved_task_again is not None
    assert retrieved_task_again.name == "Sample Task"


@pytest.mark.asyncio
async def test_get_task_not_found(store: InMemoryMetadataStore):
    """Test retrieving a non-existent task raises TaskNotFoundError."""
    non_existent_id = f"task_{uuid.uuid4()}" # Use string ID format
    with pytest.raises(TaskNotFoundError) as excinfo:
        await store.get_task(non_existent_id)
    assert non_existent_id in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_task_status(store: InMemoryMetadataStore, sample_task: Task):
    """Test updating the status of a task."""
    await store.add_task(sample_task)
    task_id = sample_task.task_id
    task_before_update = await store.get_task(task_id)
    assert task_before_update is not None
    original_updated_at = task_before_update.updated_at

    # Allow some time to pass to ensure updated_at changes
    time.sleep(0.01)

    updated_task = await store.update_task_status(task_id, TaskStatus.RUNNING)

    assert updated_task is not None
    assert updated_task.status == TaskStatus.RUNNING
    assert updated_task.updated_at > original_updated_at

    # Verify change in store
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.status == TaskStatus.RUNNING
    assert retrieved_task.updated_at == updated_task.updated_at


@pytest.mark.asyncio
async def test_update_task_status_not_found(store: InMemoryMetadataStore):
    """Test updating status of a non-existent task raises TaskNotFoundError."""
    non_existent_id = uuid.uuid4()
    # Expect TaskNotFoundError when task is not found
    with pytest.raises(TaskNotFoundError) as excinfo:
        await store.update_task_status(non_existent_id, TaskStatus.FAILED)
    assert str(non_existent_id) in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_task_output_result(store: InMemoryMetadataStore, sample_task: Task):
    """Test updating the result of a task."""
    await store.add_task(sample_task)
    task_id = sample_task.task_id
    task_before_update = await store.get_task(task_id)
    assert task_before_update is not None
    original_updated_at = task_before_update.updated_at
    result_data = {"output": "success", "value": 123}

    time.sleep(0.01)
    # Use kwargs for clarity and correct signature
    updated_task = await store.update_task_output(task_id=task_id, result=result_data)

    assert updated_task is not None
    # Check attributes directly now that signature is fixed
    assert updated_task.result == result_data
    assert updated_task.error_message is None
    assert updated_task.status == TaskStatus.COMPLETED # Status should update
    assert updated_task.updated_at > original_updated_at

    # Verify change in store
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.result == result_data
    assert retrieved_task.status == TaskStatus.COMPLETED
    assert retrieved_task.updated_at == updated_task.updated_at


@pytest.mark.asyncio
async def test_update_task_output_error(store: InMemoryMetadataStore, sample_task: Task):
    """Test updating the error message of a task."""
    await store.add_task(sample_task)
    task_id = sample_task.task_id
    task_before_update = await store.get_task(task_id)
    assert task_before_update is not None
    original_updated_at = task_before_update.updated_at
    error_msg = "Something went wrong"

    time.sleep(0.01)
    updated_task = await store.update_task_output(task_id=task_id, error_message=error_msg)

    assert updated_task is not None
    # Check attributes directly using model_dump().get()
    assert updated_task.model_dump().get('result') is None # Result should be None when error occurs
    assert updated_task.error_message == error_msg
    # Explicitly compare enum values
    assert updated_task.status.value == TaskStatus.FAILED.value # Status should update
    assert updated_task.updated_at > original_updated_at

    # Verify change in store
    retrieved_task = await store.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.error_message == error_msg
    assert retrieved_task.status == TaskStatus.FAILED
    assert retrieved_task.updated_at == updated_task.updated_at


@pytest.mark.asyncio
async def test_update_task_output_both_error_wins(store: InMemoryMetadataStore, sample_task: Task):
    """Test updating both result and error (error should take precedence for status)."""
    await store.add_task(sample_task)
    task_id = sample_task.task_id
    result_data = {"output": "partial success?"}
    error_msg = "Critical failure occurred"

    # Use kwargs for clarity
    updated_task = await store.update_task_output(
        task_id=task_id, result=result_data, error_message=error_msg
    )

    assert updated_task is not None
    # Check attributes directly
    assert updated_task.result == result_data # Result is still stored
    assert updated_task.error_message == error_msg
    assert updated_task.status == TaskStatus.FAILED # Status is FAILED due to error


@pytest.mark.asyncio
async def test_update_task_output_not_found(store: InMemoryMetadataStore):
    """Test updating output of a non-existent task raises TaskNotFoundError."""
    non_existent_id = uuid.uuid4()
    # Use kwargs for clarity and expect TaskNotFoundError
    with pytest.raises(TaskNotFoundError) as excinfo:
        await store.update_task_output(
            task_id=non_existent_id, result={"data": "test"}
        )
    # Optionally, assert the error message contains the ID
    assert str(non_existent_id) in str(excinfo.value)


@pytest.mark.asyncio
async def test_list_tasks(store: InMemoryMetadataStore):
    """Test listing tasks from the store."""
    assert await store.list_tasks() == []

    task1 = Task(name="Task 1", task_type="type1")
    task2 = Task(name="Task 2", task_type="type2")
    await store.add_task(task1)
    await store.add_task(task2)

    listed_tasks = await store.list_tasks()
    assert len(listed_tasks) == 2

    # Check if tasks with correct IDs are present (order might vary)
    listed_ids = {t.task_id for t in listed_tasks}
    assert listed_ids == {task1.task_id, task2.task_id}

    # Verify copies are returned
    original_task1_copy = deepcopy(task1)
    listed_task1 = next(t for t in listed_tasks if t.task_id == task1.task_id)
    listed_task1.name = "Modified List Task"

    retrieved_task1 = await store.get_task(task1.task_id)
    assert retrieved_task1 is not None
    assert retrieved_task1.name == original_task1_copy.name # Store shouldn't change
