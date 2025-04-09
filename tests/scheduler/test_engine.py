"""
Unit tests for the InMemoryScheduler.
"""
from unittest.mock import MagicMock, patch

import pytest

from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.models.tasks import Task, TaskStatus
from ops_core.scheduler.engine import InMemoryScheduler


@pytest.fixture
def mock_store() -> MagicMock:
    """Provides a mocked InMemoryMetadataStore."""
    return MagicMock(spec=InMemoryMetadataStore)


@pytest.fixture
def mock_mcp_client() -> MagicMock:
    """Provides a mock OpsMcpClient."""
    # Need to import OpsMcpClient for spec
    from ops_core.mcp_client.client import OpsMcpClient
    return MagicMock(spec=OpsMcpClient)


@pytest.fixture
def scheduler(mock_store: MagicMock, mock_mcp_client: MagicMock) -> InMemoryScheduler:
    """Provides an InMemoryScheduler instance with mocked store and mcp_client."""
    # Pass both required dependencies
    return InMemoryScheduler(metadata_store=mock_store, mcp_client=mock_mcp_client)


def test_scheduler_initialization(scheduler: InMemoryScheduler, mock_store: MagicMock):
    """Test that the scheduler initializes correctly with the store."""
    assert scheduler.metadata_store is mock_store # Use public attribute


@pytest.mark.asyncio
# Patch the actor's send method within the test's scope
# @patch("ops_core.scheduler.engine.execute_agent_task_actor.send") # PHASE 1 REBUILD: Commented out
async def test_submit_task(scheduler: InMemoryScheduler, mock_store: MagicMock): # PHASE 1 REBUILD: Removed mock_actor_send
    """Test submitting a task successfully."""
    task_name = "My Agent Task"
    task_type = "agent_run"
    input_data = {"prompt": "Analyze this data"}

    # Mock the get_task call that happens after add_task
    # We need to capture the task passed to add_task to return it for get_task
    added_task_capture = None

    def capture_add_task(task: Task):
        nonlocal added_task_capture
        # Simulate storing a copy
        added_task_capture = task.model_copy(deep=True)

    def mock_get_task(task_id):
        nonlocal added_task_capture
        if added_task_capture and added_task_capture.task_id == task_id:
            # Simulate returning a copy
            return added_task_capture.model_copy(deep=True)
        return None # pragma: no cover

    mock_store.add_task.side_effect = capture_add_task
    mock_store.get_task.side_effect = mock_get_task

    # Call the method under test (await the coroutine)
    returned_task = await scheduler.submit_task(
        name=task_name, task_type=task_type, input_data=input_data
    )

    # Assertions
    mock_store.add_task.assert_called_once()
    added_task = mock_store.add_task.call_args[0][0] # Get the Task object passed to add_task

    assert isinstance(added_task, Task)
    assert added_task.name == task_name
    assert added_task.task_type == task_type
    assert added_task.input_data == input_data
    assert added_task.status == TaskStatus.PENDING
    assert added_task.result is None
    assert added_task.error_message is None

    # Check the returned task matches the one added to the store
    # Note: The current submit_task returns the *new* task object directly,
    # it doesn't retrieve it again from the store after adding.
    assert returned_task is not None
    assert returned_task.task_id == added_task.task_id
    assert returned_task.name == added_task.name
    assert returned_task.status == added_task.status
    # Verify actor send was called for agent_run type
    # mock_actor_send.assert_called_once() # PHASE 1 REBUILD: Commented out


@pytest.mark.asyncio
# Patch the actor's send method here as well if submit_task calls it unconditionally
# @patch("ops_core.scheduler.engine.execute_agent_task_actor.send") # PHASE 1 REBUILD: Commented out
async def test_submit_task_store_add_failure(scheduler: InMemoryScheduler, mock_store: MagicMock): # PHASE 1 REBUILD: Removed mock_actor_send
    """Test scenario where adding the task to the store fails."""
    task_name = "Fail Add Task"
    task_type = "any_type"
    input_data = {}
    store_error_message = "Database connection refused"

    # Simulate add_task failing
    mock_store.add_task.side_effect = Exception(store_error_message)

    # Expect the original exception from the store to propagate
    with pytest.raises(Exception) as excinfo:
        await scheduler.submit_task(
            name=task_name, task_type=task_type, input_data=input_data
        )

    # Check that the raised exception is the one from the store
    assert str(excinfo.value) == store_error_message
    mock_store.add_task.assert_called_once()
    # Ensure get_task was not called if add_task failed
    mock_store.get_task.assert_not_called()
    # Ensure actor was not called if add_task failed
    # mock_actor_send.assert_not_called() # PHASE 1 REBUILD: Commented out
