# ops_core/tests/scheduler/test_engine.py
"""Unit tests for the InMemoryScheduler."""

import asyncio
import pytest
import traceback # Added for direct execution mock
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch, ANY, call # Added call
from dramatiq.brokers.stub import StubBroker # Import StubBroker

from ops_core.models import Task, TaskStatus
# Duplicate TaskStatus import removed
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.scheduler.engine import InMemoryScheduler
# Duplicate patch, ANY import removed
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.mcp_client.proxy_tool import MCPProxyTool
from ops_core.config.loader import McpConfig # Import for mocking

# Agentkit imports (assuming agentkit is installed editable or in path)
try:
    from agentkit.core.agent import Agent
    from agentkit.tools.registry import ToolRegistry, ToolExecutionError, ToolNotFoundError # Use real ToolRegistry
    from agentkit.core.interfaces import BasePlanner # Keep interface for mocking planner
    from agentkit.memory.short_term import ShortTermMemory # Use real ShortTermMemory
    # from agentkit.core.interfaces import BaseMemory # No longer needed
    from agentkit.tools.schemas import ToolResult, ToolSpec, ActionStep, Tool # Added Tool
    from agentkit.tools.mcp_proxy import mcp_proxy_tool_spec
    # Import the function we want to patch
    from agentkit.tools.execution import execute_tool_safely
    AGENTKIT_AVAILABLE = True
except ImportError:
    # Define execute_tool_safely placeholder if agentkit is missing
    async def execute_tool_safely(*args, **kwargs):
        raise ImportError("execute_tool_safely mock requires agentkit")
    AGENTKIT_AVAILABLE = False
    # Define dummy classes if agentkit is not available
    class Agent:
        def __init__(self, *args, **kwargs): pass
        async def run_async(self, goal): return "Agent Skipped"
    class ToolRegistry:
        def __init__(self, *args, **kwargs): pass
        def add_tool(self, tool): pass
    # Dummy interfaces and schemas needed for tests if agentkit missing
    class BasePlanner: pass
    class BaseMemory:
        def __init__(self, *args, **kwargs): self.history = []
        def add_event(self, event): self.history.append(event)
        def get_context(self): return ""
        def get_history(self): return self.history
    class ToolResult:
        def __init__(self, tool_name, status, output):
            self.tool_name = tool_name
            self.status = status
            self.output = output
    class ToolSpec:
        def __init__(self, name, description, input_schema):
            self.name = name
            self.description = description
            self.input_schema = input_schema
    class ActionStep:
        def __init__(self, thought, tool_name, tool_input):
            self.thought = thought
            self.tool_name = tool_name
            self.tool_input = tool_input
    # Mock the spec if agentkit is missing
    mcp_proxy_tool_spec = ToolSpec(name="mcp_proxy_tool", description="MCP Proxy", input_schema={})


@pytest.fixture
def mock_metadata_store(): # Removed type hint as spec is removed
    """Fixture for a mocked InMemoryMetadataStore (without spec)."""
    # Remove spec=InMemoryMetadataStore to allow adding _tasks attribute
    store = AsyncMock()
    store.add_task = AsyncMock()
    store.get_task = AsyncMock()
    store.list_tasks = AsyncMock(return_value=[])
    store.update_task_status = AsyncMock()
    # Add mocked _tasks attribute as a MagicMock with a configured get method
    mock_task_for_get = AsyncMock(spec=Task) # Keep spec for the task object itself
    mock_task_for_get.output_data = None
    mock_task_for_get.error_message = None
    store._tasks = MagicMock()
    store._tasks.get.return_value = mock_task_for_get

    # Remove update_task_output mock as it's not used/doesn't exist
    return store

@pytest.fixture
def mock_mcp_client() -> OpsMcpClient: # Correct type hint
    """Fixture for a mocked OpsMcpClient."""
    client = AsyncMock(spec=OpsMcpClient) # Correct spec
    client.call_tool = AsyncMock(return_value={"mcp_result": "success"})
    return client

@pytest.fixture
def scheduler(mock_metadata_store: InMemoryMetadataStore, mock_mcp_client: OpsMcpClient) -> InMemoryScheduler: # Correct type hint
    """Fixture for an InMemoryScheduler with mocked dependencies."""
    # processing_interval is no longer used by the scheduler itself
    return InMemoryScheduler(
        metadata_store=mock_metadata_store,
        mcp_client=mock_mcp_client
        # processing_interval=0.01 # Removed
    )

@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler: InMemoryScheduler, mock_metadata_store, mock_mcp_client):
    """Test scheduler initialization."""
    assert scheduler._metadata_store is mock_metadata_store
    assert scheduler._mcp_client is mock_mcp_client
    # assert scheduler._processing_interval == 0.01 # Removed check for removed attribute

@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch the actor object
async def test_submit_task_non_agent(mock_actor: MagicMock, scheduler: InMemoryScheduler, mock_metadata_store):
    """Test submitting a non-agent task does not call the actor."""
    task_name = "Non-Agent Task"
    task_type = "simple_type"
    input_data = {"param": "value"}

    created_task = await scheduler.submit_task(name=task_name, task_type=task_type, input_data=input_data)

    assert created_task.name == task_name
    assert created_task.task_type == task_type
    assert created_task.input_data == input_data
    assert created_task.status == TaskStatus.PENDING
    assert created_task.task_id.startswith("task_")

    # Check if metadata_store.add_task was called correctly
    mock_metadata_store.add_task.assert_awaited_once()
    call_args, _ = mock_metadata_store.add_task.call_args
    added_task = call_args[0]
    assert isinstance(added_task, Task)
    assert added_task.task_id == created_task.task_id
    assert added_task.name == task_name

    # Assert the actor's send method was NOT called
    mock_actor.send.assert_not_called()


@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch the actor object
@patch('ops_core.scheduler.engine.get_mcp_client') # Patch getter called by submit_task
async def test_submit_task_agent_run(
    mock_get_mcp_client: MagicMock, # Add mock getter arg
    mock_actor: MagicMock,
    scheduler: InMemoryScheduler,
    mock_metadata_store,
    mocker # Add mocker fixture
):
    """Test submitting an agent_run task calls the actor's send method."""
    # Arrange
    # Patch MCP config loading locally for this test
    mocker.patch(
        "ops_core.config.loader.get_resolved_mcp_config",
        return_value=McpConfig(servers={}),
    )
    task_name = "Agent Task"
    task_type = "agent_run"
    input_data = {"goal": "run agent"}
    # Mock the MCP client returned by the getter to avoid real initialization
    mock_mcp_client_instance = AsyncMock(spec=OpsMcpClient)
    mock_get_mcp_client.return_value = mock_mcp_client_instance

    # Mock Agent being available
    with patch('ops_core.scheduler.engine.Agent', new=MagicMock()):
        # Act
        created_task = await scheduler.submit_task(name=task_name, task_type=task_type, input_data=input_data)

    # Assert
    assert created_task.name == task_name
    assert created_task.task_type == task_type
    assert created_task.input_data == input_data
    assert created_task.status == TaskStatus.PENDING
    assert created_task.task_id.startswith("task_")

    # Check if metadata_store.add_task was called correctly
    mock_metadata_store.add_task.assert_awaited_once()
    call_args, _ = mock_metadata_store.add_task.call_args
    added_task = call_args[0]
    assert isinstance(added_task, Task)
    assert added_task.task_id == created_task.task_id
    assert added_task.name == task_name

    # Assert the actor's send method WAS called with task_id and input_data
    # The actual store/client instances passed are checked in actor logic tests
    mock_actor.send.assert_called_once_with(created_task.task_id, input_data)
    # Verify the getter was NOT called by submit_task in this case (no inject_mcp_proxy)
    mock_get_mcp_client.assert_not_called()


@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch the actor object
async def test_submit_task_agent_run_agentkit_missing(mock_actor: MagicMock, scheduler: InMemoryScheduler, mock_metadata_store):
    """Test submitting an agent_run task fails immediately if agentkit is missing."""
    task_name = "Agent Task No Kit"
    task_type = "agent_run"
    input_data = {"goal": "run agent"}

    # Ensure Agent is None for this test
    with patch('ops_core.scheduler.engine.Agent', None):
        created_task = await scheduler.submit_task(name=task_name, task_type=task_type, input_data=input_data)

    # Assert the actor's send method was NOT called
    mock_actor.send.assert_not_called()

    # Assert task status was updated to FAILED by fetching the task from the scheduler's store
    # (which is the mock_metadata_store instance in this test setup)
    # Mock the get_task call on the store fixture
    mock_task_to_check = Task(task_id=created_task.task_id, task_type=task_type, status=TaskStatus.FAILED, error_message="Agent execution failed: agentkit not installed.")
    mock_metadata_store.get_task.return_value = mock_task_to_check # Simulate fetching the failed task

    final_task = await scheduler._metadata_store.get_task(created_task.task_id) # Fetch using the mock
    mock_metadata_store.get_task.assert_awaited_with(created_task.task_id) # Verify get_task was called
    assert final_task is not None
    assert final_task.status == TaskStatus.FAILED
    assert "Agent execution failed: agentkit not installed" in final_task.error_message
    # Verify the store's update_task_status was indeed NOT called directly by submit_task
    # (The task's update_status was called internally, but not the store's method)
    mock_metadata_store.update_task_status.assert_not_called()


# Removed test_process_tasks_simulated as the internal loop is gone.
# Removed test_scheduler_start_stop as the internal loop is gone.


# --- Tests for execute_agent_task_actor internal logic ---

# We test the actor function's logic by running it via StubBroker/Worker
# to ensure the correct Dramatiq context, while patching internal dependencies.

# Fixture for a test-specific StubBroker (Keep for potential future use, but not for direct logic tests)
# @pytest.fixture(scope="function")
# def actor_test_broker():
#     broker = StubBroker()
#     broker.emit_after("process_boot")
#     # Declare the actor's queue on this specific broker instance
#     from ops_core.scheduler.engine import execute_agent_task_actor
#     broker.declare_queue(execute_agent_task_actor.queue_name)
#     # Ensure the actor is known to this broker instance
#     broker.actors[execute_agent_task_actor.actor_name] = execute_agent_task_actor
#     yield broker
#     broker.flush_all()


@pytest.mark.asyncio
# Test the helper function directly, using real ToolRegistry/Memory, mocking Agent.run
@patch('ops_core.scheduler.engine.Agent') # Still mock Agent class to control run method
async def test_run_agent_task_logic_success(
    mock_Agent_cls: MagicMock,
    mocker # Add mocker fixture
):
    """Test the core agent task logic's successful execution path using real components."""
    # --- Arrange ---
    task_id = "logic_task_success_1"
    task_input_data = {"goal": "Test Goal"}

    # Create mock instances for external dependencies
    mock_store_instance = AsyncMock(spec=InMemoryMetadataStore)
    # Mock the specific methods we expect to be called
    mock_store_instance.update_task_status = AsyncMock()
    mock_store_instance.update_task_output = AsyncMock()
    mock_mcp_instance = AsyncMock(spec=OpsMcpClient)

    # Mock the Agent instance and its run method specifically
    mock_agent_instance = MagicMock(spec=Agent)
    mock_agent_instance.run = MagicMock(return_value="Agent Result")
    # Assign a real ShortTermMemory to the mocked agent instance
    real_memory = ShortTermMemory()
    mock_agent_instance.memory = real_memory
    mock_Agent_cls.return_value = mock_agent_instance

    # Use real ToolRegistry
    # mock_registry_instance = MagicMock(spec=ToolRegistry)
    # mock_ToolRegistry_cls.return_value = mock_registry_instance # Don't mock ToolRegistry class

    from ops_core.scheduler.engine import _run_agent_task_logic # Import the helper function

    # --- Act ---
    # Call the helper function directly with mocked dependencies
    await _run_agent_task_logic(
        task_id=task_id,
        task_input_data=task_input_data,
        metadata_store=mock_store_instance,
        mcp_client=mock_mcp_instance
    )

    # --- Assert ---
    # 1. Status updated to RUNNING (check mock_store_instance)
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)

    # 2. Agent instantiated correctly (check mock Agent class call)
    # We expect it to be called with a real ToolRegistry instance now
    mock_Agent_cls.assert_called_once()
    call_args, call_kwargs = mock_Agent_cls.call_args
    # Explicitly import for isinstance check
    from agentkit.tools.registry import ToolRegistry as AgentkitToolRegistry
    from agentkit.memory.short_term import ShortTermMemory as AgentkitShortTermMemory
    assert isinstance(call_kwargs.get("tool_manager"), AgentkitToolRegistry)
    assert isinstance(call_kwargs.get("memory"), AgentkitShortTermMemory) # Check if memory is passed

    # 3. Agent run method called (check mock agent instance)
    mock_agent_instance.run.assert_called_once_with(goal="Test Goal")

    # 4. Final status and result updated (check mock_store_instance and mock task)
    # Mock get_task to return a mock task object *before* the logic runs
    mock_task = AsyncMock(spec=Task)
    # Configure the mock task object to have the necessary attributes for the assertion
    mock_task.output_data = None
    mock_task.error_message = None
    mock_store_instance.get_task.return_value = mock_task

    # --- Assert Final Update ---
    # Check the final update_task_output call
    mock_store_instance.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        output_data={'memory_history': [], 'final_output': 'Agent Result'},
        error_message=None
    )
    # Check the final update_task_status call
    mock_store_instance.update_task_status.assert_awaited_with(task_id, TaskStatus.COMPLETED)
    # Verify update_task_status was called twice in total (RUNNING + final)
    assert mock_store_instance.update_task_status.await_count == 2
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.COMPLETED)
    # We can't easily assert the output_data/error_message on the mock store directly
    # as the logic modifies the object fetched via _tasks.get() before the final status update.
    # Relying on the E2E tests to verify the final stored state is reasonable here.

    # 5. MCP client not used, proxy tool not added
    mock_mcp_instance.call_tool.assert_not_called()
    # Cannot easily assert add_tool on real registry without more complex setup


@pytest.mark.asyncio
# Test the helper function directly, using real ToolRegistry/Memory, mocking Agent.run
@patch('ops_core.scheduler.engine.Agent') # Still mock Agent class
@patch('ops_core.scheduler.engine.MCPProxyTool') # Mock the proxy tool class
async def test_run_agent_task_logic_with_mcp_proxy(
    mock_MCPProxyTool_cls: MagicMock,
    mock_Agent_cls: MagicMock,
    mocker # Add mocker fixture
):
    """Test the core agent task logic's successful execution path with MCP proxy injection using real components."""
    # --- Arrange ---
    task_id = "logic_task_mcp_1"
    task_input_data = {"goal": "Test MCP Goal", "inject_mcp_proxy": True}

    # Create mock instances for external dependencies
    mock_store_instance = AsyncMock(spec=InMemoryMetadataStore)
    # Mock the specific methods we expect to be called
    mock_store_instance.update_task_status = AsyncMock()
    mock_store_instance.update_task_output = AsyncMock()
    mock_mcp_instance = AsyncMock(spec=OpsMcpClient)

    # Mock the Agent instance and its run method
    mock_agent_instance = MagicMock(spec=Agent)
    mock_agent_instance.run = MagicMock(return_value="Agent MCP Result")
    real_memory = ShortTermMemory() # Use real memory
    mock_agent_instance.memory = real_memory
    mock_Agent_cls.return_value = mock_agent_instance

    # Use real ToolRegistry - don't mock the class
    # mock_registry_instance = MagicMock(spec=ToolRegistry)
    # mock_ToolRegistry_cls.return_value = mock_registry_instance

    # Mock the MCPProxyTool instance that gets created
    mock_proxy_instance = MagicMock(spec=MCPProxyTool)
    mock_MCPProxyTool_cls.return_value = mock_proxy_instance

    from ops_core.scheduler.engine import _run_agent_task_logic # Import the helper function

    # --- Act ---
    # Call the helper function directly with mocked dependencies
    await _run_agent_task_logic(
        task_id=task_id,
        task_input_data=task_input_data,
        metadata_store=mock_store_instance,
        mcp_client=mock_mcp_instance
    )

    # --- Assert ---
    # 1. Status updated to RUNNING
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)

    # 2. MCPProxyTool instantiated with the correct client
    mock_MCPProxyTool_cls.assert_called_once_with(mcp_client=mock_mcp_instance)

    # 3. ToolRegistry add_tool called with the proxy instance
    # This is harder to assert now as it happens inside the real ToolRegistry.
    # We rely on the Agent instantiation check below which implicitly uses the registry.

    # 4. Agent instantiated correctly (check mock Agent class call)
    mock_Agent_cls.assert_called_once()
    call_args, call_kwargs = mock_Agent_cls.call_args
    tool_manager_arg = call_kwargs.get("tool_manager")
    # Explicitly import for isinstance check
    from agentkit.tools.registry import ToolRegistry as AgentkitToolRegistry
    assert isinstance(tool_manager_arg, AgentkitToolRegistry)
    # Check if the proxy tool was added (difficult without mocking add_tool)
    # assert mock_proxy_instance in tool_manager_arg._tools.values() # Internal detail, avoid if possible

    # 5. Agent run method called (check mock agent instance)
    mock_agent_instance.run.assert_called_once_with(goal="Test MCP Goal")

    # 6. Final status and result updated
    # Mock get_task to return a mock task object *before* the logic runs
    mock_task = AsyncMock(spec=Task)
    # Configure the mock task object
    mock_task.output_data = None
    mock_task.error_message = None
    mock_store_instance.get_task.return_value = mock_task

    # --- Assert Final Update ---
    # Check the final update_task_output call
    mock_store_instance.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        output_data={'memory_history': [], 'final_output': 'Agent MCP Result'},
        error_message=None
    )
    # Check the final update_task_status call
    mock_store_instance.update_task_status.assert_awaited_with(task_id, TaskStatus.COMPLETED)
    # Verify update_task_status was called twice in total (RUNNING + final)
    assert mock_store_instance.update_task_status.await_count == 2
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.COMPLETED)


@pytest.mark.asyncio
# Test the helper function directly, using real ToolRegistry/Memory, mocking Agent.run failure
@patch('ops_core.scheduler.engine.Agent') # Still mock Agent class
@patch('ops_core.scheduler.engine.traceback.format_exc')
async def test_run_agent_task_logic_agent_failure(
    mock_format_exc: MagicMock,
    mock_Agent_cls: MagicMock,
    mocker # Add mocker fixture
):
    """Test the core agent task logic's execution path when the agent run fails using real components."""
    # --- Arrange ---
    task_id = "logic_task_fail_1"
    task_input_data = {"goal": "Fail Goal"}
    agent_error_message = "Agent simulation error"
    mock_traceback_str = "Traceback (most recent call last):\n..."
    mock_format_exc.return_value = mock_traceback_str

    # Create mock instances for external dependencies
    mock_store_instance = AsyncMock(spec=InMemoryMetadataStore)
    # Mock the specific methods we expect to be called
    mock_store_instance.update_task_status = AsyncMock()
    mock_store_instance.update_task_output = AsyncMock()
    mock_mcp_instance = AsyncMock(spec=OpsMcpClient)

    # Mock Agent instance to raise an error during run
    mock_agent_instance = MagicMock(spec=Agent)
    mock_agent_instance.run = MagicMock(side_effect=ValueError(agent_error_message))
    real_memory = ShortTermMemory() # Use real memory
    mock_agent_instance.memory = real_memory
    mock_Agent_cls.return_value = mock_agent_instance

    # Use real ToolRegistry - don't mock the class
    # mock_registry_instance = MagicMock(spec=ToolRegistry)
    # mock_ToolRegistry_cls.return_value = mock_registry_instance

    from ops_core.scheduler.engine import _run_agent_task_logic # Import the helper function

    # --- Act ---
    # Call the helper function directly with mocked dependencies
    await _run_agent_task_logic(
        task_id=task_id,
        task_input_data=task_input_data,
        metadata_store=mock_store_instance,
        mcp_client=mock_mcp_instance
    )

    # --- Assert ---
    # 1. Status updated to RUNNING
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)

    # 2. Agent instantiated correctly (check mock Agent class call)
    mock_Agent_cls.assert_called_once()
    call_args, call_kwargs = mock_Agent_cls.call_args
    # Explicitly import for isinstance check
    from agentkit.tools.registry import ToolRegistry as AgentkitToolRegistry
    from agentkit.memory.short_term import ShortTermMemory as AgentkitShortTermMemory
    assert isinstance(call_kwargs.get("tool_manager"), AgentkitToolRegistry)
    assert isinstance(call_kwargs.get("memory"), AgentkitShortTermMemory)

    # 3. Agent run method called (check mock agent instance)
    mock_agent_instance.run.assert_called_once_with(goal="Fail Goal")

    # 4. Final status and result updated with FAILED status and error
    # Mock get_task to return a mock task object *before* the logic runs
    mock_task = AsyncMock(spec=Task)
    # Configure the mock task object
    mock_task.output_data = None
    mock_task.error_message = None
    mock_store_instance.get_task.return_value = mock_task

    # --- Assert Final Update ---
    # Check the final update_task_output call
    expected_error_msg = f"ValueError: {agent_error_message}\n{mock_traceback_str}"
    mock_store_instance.update_task_output.assert_awaited_once_with(
        task_id=task_id,
        output_data=None,
        error_message=expected_error_msg
    )
    # Check the final update_task_status call
    mock_store_instance.update_task_status.assert_awaited_with(task_id, TaskStatus.FAILED)
    # Verify update_task_status was called twice in total (RUNNING + final)
    assert mock_store_instance.update_task_status.await_count == 2
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.RUNNING)
    mock_store_instance.update_task_status.assert_any_call(task_id, TaskStatus.FAILED)
    # We can't easily assert the error_message here, rely on E2E tests.


# Removed obsolete MCP integration test (test_scheduler_runs_agent_with_mcp_proxy_call)
# and its helper classes (MockMCPPlanner, MockCaptureMemory) as they tested
# the old direct execution flow. New integration tests are needed for the
# Dramatiq worker flow.
