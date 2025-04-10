"""
Unit tests for the InMemoryScheduler.
"""
from unittest.mock import MagicMock, patch

import pytest

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ops_core.metadata.sql_store import SqlMetadataStore # Import the real store
from ops_core.metadata.base import BaseMetadataStore # Import base for type hints
from ops_core.metadata.store import TaskNotFoundError # Keep error
from ops_core.models.tasks import Task, TaskStatus
from ops_core.scheduler.engine import InMemoryScheduler, _run_agent_task_logic # Import the function
from agentkit.core.interfaces import BaseLlmClient, BasePlanner # Import interfaces for mocking
from ops_core.mcp_client.client import OpsMcpClient # Import for mocking spec
from agentkit.core.agent import Agent # Import for mocking spec
from agentkit.memory.short_term import ShortTermMemory # Import for mocking spec
# Import the database session fixture if not already globally available via conftest
# Assuming db_session is available from conftest.py


# Remove mock_store fixture
# @pytest.fixture
# def mock_store() -> MagicMock:
#     """Provides a mocked InMemoryMetadataStore."""
#     return MagicMock(spec=InMemoryMetadataStore)


@pytest.fixture
def mock_mcp_client() -> MagicMock:
    """Provides a mock OpsMcpClient."""
    # Need to import OpsMcpClient for spec
    from ops_core.mcp_client.client import OpsMcpClient
    return MagicMock(spec=OpsMcpClient)


@pytest.fixture
def scheduler(db_session: AsyncSession, mock_mcp_client: MagicMock) -> InMemoryScheduler:
    """Provides an InMemoryScheduler instance with a real SqlMetadataStore."""
    # Create a real store instance using the test session
    sql_store = SqlMetadataStore(db_session)
    # Pass the real store and mock client
    return InMemoryScheduler(metadata_store=sql_store, mcp_client=mock_mcp_client)


def test_scheduler_initialization(scheduler: InMemoryScheduler):
    """Test that the scheduler initializes correctly with the store."""
    assert isinstance(scheduler.metadata_store, SqlMetadataStore)


@pytest.mark.asyncio
# Patch the actor's send method within the test's scope
@patch("ops_core.scheduler.engine.execute_agent_task_actor.send")
async def test_submit_task(
    mock_actor_send: MagicMock,
    scheduler: InMemoryScheduler, # Uses the updated fixture with SqlMetadataStore
    db_session: AsyncSession # Inject db session for verification
):
    """Test submitting a task successfully adds it to the database."""
    task_name = "My Agent Task DB"
    task_type = "agent_run"
    input_data = {"prompt": "Analyze this data"}

    # Call the method under test (await the coroutine)
    returned_task = await scheduler.submit_task(
        name=task_name, task_type=task_type, input_data=input_data
    )

    # Assertions
    assert isinstance(returned_task, Task)
    assert returned_task.name == task_name
    assert returned_task.task_type == task_type
    assert returned_task.input_data == input_data
    assert returned_task.status == TaskStatus.PENDING
    assert returned_task.result is None
    assert returned_task.error_message is None
    assert returned_task.task_id is not None

    # Verify the task exists in the database
    stmt = select(Task).where(Task.task_id == returned_task.task_id)
    result = await db_session.execute(stmt)
    db_task = result.scalar_one_or_none()

    assert db_task is not None
    assert db_task.task_id == returned_task.task_id
    assert db_task.name == task_name
    assert db_task.status == TaskStatus.PENDING

    # Verify actor send was called for agent_run type
    mock_actor_send.assert_called_once_with(
        task_id=returned_task.task_id,
        goal=input_data.get("goal", "No goal specified"), # Match goal extraction
        input_data=input_data
    )


@pytest.mark.asyncio
# Patch the actor's send method here as well if submit_task calls it unconditionally
@patch("ops_core.scheduler.engine.execute_agent_task_actor.send")
# Patch the add_task method of the store used by the scheduler
@patch.object(SqlMetadataStore, "add_task", new_callable=AsyncMock)
async def test_submit_task_store_add_failure(
    mock_add_task: AsyncMock, # Mock for SqlMetadataStore.add_task
    mock_actor_send: MagicMock,
    scheduler: InMemoryScheduler, # Uses the updated fixture
    db_session: AsyncSession # Keep session for scheduler init if needed
):
    """Test scenario where adding the task to the store fails."""
    task_name = "Fail Add Task DB"
    task_type = "any_type"
    input_data = {}
    db_error_message = "Simulated DB add_task error"

    # Simulate add_task failing
    mock_add_task.side_effect = Exception(db_error_message)

    # Expect the original exception from add_task to propagate
    with pytest.raises(Exception) as excinfo:
        await scheduler.submit_task(
            name=task_name, task_type=task_type, input_data=input_data
        )

    # Check that the raised exception is the one from add_task
    assert str(excinfo.value) == db_error_message
    # Ensure actor was not called if add_task failed
    mock_actor_send.assert_not_called()
    # Ensure add_task was called
    mock_add_task.assert_awaited_once()


# --- Tests for _run_agent_task_logic ---

@pytest.mark.asyncio
async def test_run_agent_task_logic_success(mocker):
    """Test the _run_agent_task_logic function for a successful agent run with mocked store."""
    task_id = "logic_success_mock_db"
    goal = "Test successful logic run with mocked DB"
    input_data = {"some": "data"}
    agent_result = {"status": "Success", "output": "Agent completed"}
    memory_content = ["memory context"]

    # Mock the store instance that will be passed to the function
    mock_store_instance = AsyncMock(spec=BaseMetadataStore)
    mock_store_instance.update_task_status = AsyncMock()
    mock_store_instance.update_task_output = AsyncMock()
    # No need to mock get_task here as it's not called directly by this logic path

    # Mock other dependencies
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient))
    mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner))
    mock_agent_patch = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch.return_value
    mock_agent_instance.run = AsyncMock(return_value=agent_result)
    mock_memory_instance = mocker.patch("ops_core.scheduler.engine.ShortTermMemory", return_value=MagicMock(spec=ShortTermMemory)).return_value
    mock_memory_instance.get_context = AsyncMock(return_value=memory_content)
    mock_agent_instance.memory = mock_memory_instance
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")
    mocker.patch("ops_core.scheduler.engine.MCPProxyTool")

    # Call the function under test, passing the mocked store
    await _run_agent_task_logic(
        task_id=task_id,
        goal=goal,
        input_data=input_data,
        metadata_store=mock_store_instance, # Pass the mock store instance
        mcp_client=mock_mcp_client
    )

    # Assertions
    # Check Agent instantiation and run
    mock_agent_patch.assert_called_once() # Agent class instantiated
    mock_agent_instance.run.assert_awaited_once_with(goal=goal) # Agent run called
    mock_memory_instance.get_context.assert_awaited_once() # Memory context retrieved

    # Verify store method calls
    expected_result_data = {
        "agent_outcome": agent_result,
        "memory_history": memory_content,
    }
    # Check status updates: RUNNING then COMPLETED
    mock_store_instance.update_task_status.assert_has_awaits([
        call(task_id, TaskStatus.RUNNING),
        call(task_id, TaskStatus.COMPLETED)
    ], any_order=False) # Ensure order is correct

    # Check output update (only called once at the end)
    mock_store_instance.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        result=expected_result_data
        # error_message=None # This argument was removed from update_task_output
    )


@pytest.mark.asyncio
async def test_run_agent_task_logic_agent_failure(mocker):
    """Test _run_agent_task_logic when the agent.run() call fails, with mocked store."""
    task_id = "logic_agent_fail_mock_db"
    goal = "Test agent failure with mocked DB"
    input_data = {}
    agent_error_message = "Agent run failed!"

    # Mock the store instance
    mock_store_instance = AsyncMock(spec=BaseMetadataStore)
    mock_store_instance.update_task_status = AsyncMock()
    mock_store_instance.update_task_output = AsyncMock()

    # Mock other dependencies
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient))
    mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner))
    mock_agent_patch_fail = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch_fail.return_value
    # Simulate agent run raising an exception
    mock_agent_instance.run = AsyncMock(side_effect=Exception(agent_error_message))
    mocker.patch("ops_core.scheduler.engine.ShortTermMemory") # Mock memory, context won't be fetched on failure
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")

    # Call the function, passing the mock store
    await _run_agent_task_logic(
        task_id=task_id,
        goal=goal,
        input_data=input_data,
        metadata_store=mock_store_instance, # Pass mock store
        mcp_client=mock_mcp_client
    )

    # Assertions
    mock_agent_instance.run.assert_awaited_once_with(goal=goal)

    # Verify store method calls
    # Check status updates: RUNNING then FAILED
    mock_store_instance.update_task_status.assert_has_awaits([
        call(task_id, TaskStatus.RUNNING),
        # Use keyword arguments for the second call to match actual usage
        call(task_id=task_id, status=TaskStatus.FAILED, error_message=agent_error_message)
    ], any_order=False)

    # Check output update (called once in exception handler)
    mock_store_instance.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        result={"error": "Agent execution failed unexpectedly."} # Check error result
    )


@pytest.mark.asyncio
async def test_run_agent_task_logic_task_not_found(mocker):
    """Test _run_agent_task_logic when the initial task update fails due to TaskNotFoundError."""
    task_id = "task_logic_not_found_mock_db" # Non-existent ID
    goal = "Test task not found with mocked DB"
    input_data = {}

    # Mock the store instance
    mock_store_instance = AsyncMock(spec=BaseMetadataStore)
    # Simulate the first status update failing
    mock_store_instance.update_task_status.side_effect = TaskNotFoundError(f"Task {task_id} not found")
    mock_store_instance.update_task_output = AsyncMock() # Should not be called

    # Mock other dependencies (agent etc. shouldn't be called)
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mocker.patch("ops_core.scheduler.engine.get_llm_client")
    mocker.patch("ops_core.scheduler.engine.get_planner")
    mock_agent_patch_notfound = mocker.patch("ops_core.scheduler.engine.Agent")

    # Call the function with the non-existent task_id, passing mock store
    # The function should handle TaskNotFoundError internally and log it, not raise it.
    await _run_agent_task_logic(
        task_id=task_id,
        goal=goal,
        input_data=input_data,
        metadata_store=mock_store_instance, # Pass mock store
        mcp_client=mock_mcp_client
    )

    # Assertions
    # Verify the first status update was attempted (which raises the internal error)
    mock_store_instance.update_task_status.assert_awaited_once_with(task_id, TaskStatus.RUNNING)
    # Agent should not be instantiated or run because the error happened early
    mock_agent_patch_notfound.assert_not_called()
    # Verify output update was NOT called
    mock_store_instance.update_task_output.assert_not_awaited()
