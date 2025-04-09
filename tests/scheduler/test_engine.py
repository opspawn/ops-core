"""
Unit tests for the InMemoryScheduler.
"""
from unittest.mock import MagicMock, patch

import pytest

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call

import pytest

from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError
from ops_core.models.tasks import Task, TaskStatus
from ops_core.scheduler.engine import InMemoryScheduler, _run_agent_task_logic # Import the function
from agentkit.core.interfaces import BaseLlmClient, BasePlanner # Import interfaces for mocking
from ops_core.mcp_client.client import OpsMcpClient # Import for mocking spec
from agentkit.core.agent import Agent # Import for mocking spec
from agentkit.memory.short_term import ShortTermMemory # Import for mocking spec


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
@patch("ops_core.scheduler.engine.execute_agent_task_actor.send")
async def test_submit_task(mock_actor_send: MagicMock, scheduler: InMemoryScheduler, mock_store: MagicMock):
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
    mock_actor_send.assert_called_once()


@pytest.mark.asyncio
# Patch the actor's send method here as well if submit_task calls it unconditionally
@patch("ops_core.scheduler.engine.execute_agent_task_actor.send")
async def test_submit_task_store_add_failure(mock_actor_send: MagicMock, scheduler: InMemoryScheduler, mock_store: MagicMock):
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
    mock_actor_send.assert_not_called()


# --- Tests for _run_agent_task_logic ---

@pytest.mark.asyncio
async def test_run_agent_task_logic_success(mocker):
    """Test the _run_agent_task_logic function for a successful agent run."""
    task_id = "task_logic_success"
    goal = "Test successful logic run"
    input_data = {"some": "data"}
    agent_result = {"status": "Success", "output": "Agent completed"}
    memory_content = ["memory context"]

    # Mock dependencies obtained via getters within the function
    mock_store = mocker.patch("ops_core.scheduler.engine.get_metadata_store", return_value=AsyncMock(spec=InMemoryMetadataStore)).return_value
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mock_mcp_client._is_running = True # Simulate running MCP client

    # Mock dependencies instantiated within the function
    mock_llm_client = mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient)).return_value
    mock_planner = mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner)).return_value
    # Patch the Agent class and capture the patch object
    mock_agent_patch = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch.return_value # Get the instance returned by the patch
    # Explicitly mock the run method as an AsyncMock
    mock_agent_instance.run = AsyncMock(return_value=agent_result)
    # Mock the memory instance created within the logic and its get_context method
    mock_memory_instance = mocker.patch("ops_core.scheduler.engine.ShortTermMemory", return_value=MagicMock(spec=ShortTermMemory)).return_value
    mock_memory_instance.get_context = AsyncMock(return_value=memory_content) # Make get_context async
    # Assign the mocked memory instance to the mocked agent instance
    mock_agent_instance.memory = mock_memory_instance
    # Mock ToolRegistry and MCPProxyTool if needed, assume default behavior is okay for now
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")
    mocker.patch("ops_core.scheduler.engine.MCPProxyTool")

    # Call the function under test
    await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=input_data)

    # Assertions
    # Check status updates
    mock_store.update_task_status.assert_has_awaits([
        call(task_id, TaskStatus.RUNNING),
        call(task_id, TaskStatus.COMPLETED) # Final status update
    ])

    # Check Agent instantiation and run
    mock_agent_patch.assert_called_once() # Check the patch object (representing the class)
    mock_agent_instance.run.assert_awaited_once_with(goal=goal)

    # Check memory context retrieval
    mock_memory_instance.get_context.assert_awaited_once()

    # Check final output update
    expected_result_data = {
        "agent_outcome": agent_result,
        "memory_history": memory_content,
    }
    mock_store.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        result=expected_result_data,
        error_message=None
    )


@pytest.mark.asyncio
async def test_run_agent_task_logic_agent_failure(mocker):
    """Test _run_agent_task_logic when the agent.run() call fails."""
    task_id = "task_logic_agent_fail"
    goal = "Test agent failure"
    input_data = {}
    agent_error_message = "Agent run failed!"

    # Mock dependencies
    mock_store = mocker.patch("ops_core.scheduler.engine.get_metadata_store", return_value=AsyncMock(spec=InMemoryMetadataStore)).return_value
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mock_mcp_client._is_running = True # Set _is_running attribute
    mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient))
    mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner))
    # Patch the Agent class and capture the patch object
    mock_agent_patch_fail = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch_fail.return_value # Get the instance
    # Simulate agent run raising an exception using AsyncMock
    mock_agent_instance.run = AsyncMock(side_effect=Exception(agent_error_message))
    mocker.patch("ops_core.scheduler.engine.ShortTermMemory")
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")

    # Call the function
    await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=input_data)

    # Assertions
    mock_store.update_task_status.assert_has_awaits([
        call(task_id, TaskStatus.RUNNING),
        call(task_id, TaskStatus.FAILED) # Final status update
    ])
    # Use assert_awaited_once_with for AsyncMock
    mock_agent_instance.run.assert_awaited_once_with(goal=goal)
    # Check final output update reflects the error
    mock_store.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        result={"error": "Agent execution failed unexpectedly."},
        error_message=agent_error_message
    )


@pytest.mark.asyncio
async def test_run_agent_task_logic_task_not_found(mocker):
    """Test _run_agent_task_logic when the initial task is not found."""
    task_id = "task_logic_not_found"
    goal = "Test task not found"
    input_data = {}

    # Mock store to raise TaskNotFoundError on the first status update
    mock_store = mocker.patch("ops_core.scheduler.engine.get_metadata_store", return_value=AsyncMock(spec=InMemoryMetadataStore)).return_value
    mock_store.update_task_status.side_effect = TaskNotFoundError(f"Task {task_id} not found")
    # Mock other getters just in case
    mocker.patch("ops_core.scheduler.engine.get_mcp_client")
    mocker.patch("ops_core.scheduler.engine.get_llm_client")
    mocker.patch("ops_core.scheduler.engine.get_planner")
    # Patch the Agent class but don't need the instance here
    mock_agent_patch_notfound = mocker.patch("ops_core.scheduler.engine.Agent")

    # Call the function
    await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=input_data)

    # Assertions
    # Only the first status update should be attempted
    mock_store.update_task_status.assert_awaited_once_with(task_id, TaskStatus.RUNNING)
    # Agent should not be instantiated or run
    mock_agent_patch_notfound.assert_not_called()
    # Output should not be updated
    mock_store.update_task_output.assert_not_called()
