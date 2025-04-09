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
# Patch the session commit method to simulate DB failure
@patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock)
async def test_submit_task_store_add_failure(
    mock_commit: AsyncMock,
    mock_actor_send: MagicMock,
    scheduler: InMemoryScheduler, # Uses the updated fixture
    db_session: AsyncSession # Inject session for context
):
    """Test scenario where adding the task to the store fails (DB commit fails)."""
    task_name = "Fail Add Task DB"
    task_type = "any_type"
    input_data = {}
    db_error_message = "Simulated DB commit error"

    # Simulate commit failing
    mock_commit.side_effect = Exception(db_error_message)

    # Expect the original exception from the DB commit to propagate
    with pytest.raises(Exception) as excinfo:
        await scheduler.submit_task(
            name=task_name, task_type=task_type, input_data=input_data
        )

    # Check that the raised exception is the one from the commit
    assert str(excinfo.value) == db_error_message
    # Ensure actor was not called if add_task failed
    mock_actor_send.assert_not_called()


# --- Tests for _run_agent_task_logic ---

@pytest.mark.asyncio
async def test_run_agent_task_logic_success(mocker, db_session: AsyncSession):
    """Test the _run_agent_task_logic function for a successful agent run using SqlMetadataStore."""
    task_name = "logic_success_db"
    goal = "Test successful logic run with DB"
    input_data = {"some": "data"}
    agent_result = {"status": "Success", "output": "Agent completed"}
    memory_content = ["memory context"]

    # Create a real store instance for the test
    sql_store = SqlMetadataStore() # No session needed in constructor

    # Create a task in the DB first
    initial_task = Task(name=task_name, task_type="agent_run", input_data=input_data, status=TaskStatus.PENDING)
    await sql_store.add_task(initial_task)
    task_id = initial_task.task_id # Get the generated ID

    # Mock dependencies obtained via getters within the function
    # No longer need to mock get_metadata_store
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    # mock_mcp_client._is_running = True # Check removed in latest engine code

    # Mock dependencies instantiated within the function
    mock_llm_client = mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient)).return_value
    mock_planner = mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner)).return_value
    mock_agent_patch = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch.return_value
    mock_agent_instance.run = AsyncMock(return_value=agent_result)
    mock_memory_instance = mocker.patch("ops_core.scheduler.engine.ShortTermMemory", return_value=MagicMock(spec=ShortTermMemory)).return_value
    mock_memory_instance.get_context = AsyncMock(return_value=memory_content)
    mock_agent_instance.memory = mock_memory_instance
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")
    mocker.patch("ops_core.scheduler.engine.MCPProxyTool")

    # Call the function under test, passing the real store
    await _run_agent_task_logic(
        task_id=task_id,
        goal=goal,
        input_data=input_data,
        metadata_store=sql_store, # Pass the real store
        mcp_client=mock_mcp_client
    )

    # Assertions
    # Check Agent instantiation and run
    mock_agent_patch.assert_called_once()
    mock_agent_instance.run.assert_awaited_once_with(goal=goal)
    mock_memory_instance.get_context.assert_awaited_once()

    # Verify task status and output in the database
    db_task = await sql_store.get_task(task_id)
    assert db_task is not None
    assert db_task.status == TaskStatus.COMPLETED
    expected_result_data = {
        "agent_outcome": agent_result,
        "memory_history": memory_content,
    }
    assert db_task.result == expected_result_data
    assert db_task.error_message is None


@pytest.mark.asyncio
async def test_run_agent_task_logic_agent_failure(mocker, db_session: AsyncSession):
    """Test _run_agent_task_logic when the agent.run() call fails, using SqlMetadataStore."""
    task_name = "logic_agent_fail_db"
    goal = "Test agent failure with DB"
    input_data = {}
    agent_error_message = "Agent run failed!"

    # Create a real store instance
    sql_store = SqlMetadataStore() # No session needed in constructor

    # Create a task in the DB first
    initial_task = Task(name=task_name, task_type="agent_run", input_data=input_data, status=TaskStatus.PENDING)
    await sql_store.add_task(initial_task)
    task_id = initial_task.task_id

    # Mock dependencies
    # No longer need to mock get_metadata_store
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    # mock_mcp_client._is_running = True # Check removed
    mocker.patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient))
    mocker.patch("ops_core.scheduler.engine.get_planner", return_value=MagicMock(spec=BasePlanner))
    mock_agent_patch_fail = mocker.patch("ops_core.scheduler.engine.Agent", return_value=AsyncMock(spec=Agent))
    mock_agent_instance = mock_agent_patch_fail.return_value
    # Simulate agent run raising an exception
    mock_agent_instance.run = AsyncMock(side_effect=Exception(agent_error_message))
    mocker.patch("ops_core.scheduler.engine.ShortTermMemory")
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")

    # Call the function, passing the real store
    await _run_agent_task_logic(
        task_id=task_id,
        goal=goal,
        input_data=input_data,
        metadata_store=sql_store, # Pass real store
        mcp_client=mock_mcp_client
    )

    # Assertions
    mock_agent_instance.run.assert_awaited_once_with(goal=goal)

    # Verify task status and output in the database
    db_task = await sql_store.get_task(task_id)
    assert db_task is not None
    assert db_task.status == TaskStatus.FAILED
    assert db_task.result == {"error": "Agent execution failed unexpectedly."}
    assert db_task.error_message == agent_error_message


@pytest.mark.asyncio
async def test_run_agent_task_logic_task_not_found(mocker, db_session: AsyncSession):
    """Test _run_agent_task_logic when the initial task is not found in SqlMetadataStore."""
    task_id = "task_logic_not_found_db" # Non-existent ID
    goal = "Test task not found with DB"
    input_data = {}

    # Create a real store instance
    sql_store = SqlMetadataStore() # No session needed in constructor

    # Mock other dependencies (agent etc. shouldn't be called)
    mock_mcp_client = mocker.patch("ops_core.scheduler.engine.get_mcp_client", return_value=AsyncMock(spec=OpsMcpClient)).return_value
    mocker.patch("ops_core.scheduler.engine.get_llm_client")
    mocker.patch("ops_core.scheduler.engine.get_planner")
    mock_agent_patch_notfound = mocker.patch("ops_core.scheduler.engine.Agent")

    # Call the function with the non-existent task_id and real store
    # Expect TaskNotFoundError during the first status update
    with pytest.raises(TaskNotFoundError):
        await _run_agent_task_logic(
            task_id=task_id,
            goal=goal,
            input_data=input_data,
            metadata_store=sql_store, # Pass real store
            mcp_client=mock_mcp_client
        )

    # Assertions
    # Agent should not be instantiated or run
    mock_agent_patch_notfound.assert_not_called()

    # Verify task does not exist in DB (it shouldn't have been created)
    db_task = await sql_store.get_task(task_id)
    assert db_task is None
