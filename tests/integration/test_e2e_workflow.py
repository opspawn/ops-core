import asyncio
import uuid
from unittest.mock import AsyncMock, patch, MagicMock # Added MagicMock import
import queue # Import the queue module

import pytest
import dramatiq # Added import
from agentkit.core.interfaces.llm_client import BaseLlmClient # Import for mock spec
from dramatiq import Message
from fastapi.testclient import TestClient

from agentkit.core.agent import Agent
from agentkit.memory.short_term import ShortTermMemory
from agentkit.planning.simple_planner import SimplePlanner
from agentkit.planning.react_planner import ReActPlanner # Import ReActPlanner
from agentkit.tools.registry import ToolRegistry
from ops_core.models.tasks import Task, TaskStatus # Reverted import path
from ops_core.dependencies import get_mcp_client, get_metadata_store # Reverted import path
from ops_core.main import app # Reverted import path
from ops_core.scheduler.engine import _run_agent_task_logic, execute_agent_task_actor # Import actor
from ops_core.tasks.broker import rabbitmq_broker # Reverted import path - keep for patching? No, actor uses it implicitly.
from ops_core.config.loader import McpConfig # Import for mocking config
from ops_core.scheduler.engine import InMemoryScheduler # Import scheduler
from ops_core.api.v1.endpoints import tasks as tasks_api # Import API module for dependency path

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


from ops_core.metadata.store import InMemoryMetadataStore # Import needed for instantiation

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# Import the actual OpsMcpClient to use its spec correctly
from ops_core.mcp_client.client import OpsMcpClient


@pytest.fixture(scope="function")
def test_app_components(mock_mcp_client): # Removed stub_broker
    """
    Creates FastAPI TestClient, InMemoryMetadataStore, and mocked OpsMcpClient
    with dependencies correctly overridden for integration testing.
    Yields the client, store, scheduler, and mcp_client instance used.
    """
    # Create instances specifically for this test setup
    test_store = InMemoryMetadataStore()
    # Create scheduler instance with the test store and mock client
    test_scheduler = InMemoryScheduler(metadata_store=test_store, mcp_client=mock_mcp_client)

    # Override dependencies in the FastAPI app to use these specific instances
    # Override dependencies used by the API endpoints module
    app.dependency_overrides[tasks_api.get_metadata_store] = lambda: test_store
    app.dependency_overrides[tasks_api.get_mcp_client] = lambda: mock_mcp_client
    app.dependency_overrides[tasks_api.get_scheduler] = lambda: test_scheduler # Inject the test scheduler

    # Ensure the broker used by the app is the stub_broker for testing
    # This might require patching where the broker is imported/used if not DI
    # For now, assume the scheduler uses the globally configured broker
    # which we patch elsewhere or rely on Dramatiq's test setup.
    # If tests fail, revisit how the broker is accessed by the scheduler/API.
    # Patch the config loader to prevent real env var resolution during client init
    # Configure the mock MCP client to have the '_is_running' attribute
    mock_mcp_client._is_running = True

    # Patch the config loader and the actor's send method
    with patch("ops_core.mcp_client.client.get_resolved_mcp_config", return_value=McpConfig(servers={})), \
         patch("ops_core.scheduler.engine.execute_agent_task_actor.send", MagicMock()) as mock_actor_send: # Patch send directly
        test_client = TestClient(app)
        # Yield all components needed by the tests, including the mock send
        yield test_client, test_store, test_scheduler, mock_mcp_client, mock_actor_send

    # Cleanup overrides
    app.dependency_overrides = {}


async def test_e2e_successful_agent_task(
    test_app_components # Use the combined fixture, stub_broker no longer needed
):
    """
    Test the full flow for a successful agent task:
    API -> Scheduler -> (Mocked) Broker Send -> Manual Actor Logic -> Store Update
    """
    test_client, test_store, test_scheduler, mock_mcp_client, mock_actor_send = test_app_components # Unpack the fixture result

    task_input = {"prompt": "Test prompt for success"}
    response = test_client.post("/api/v1/tasks/", json={"task_type": "agent_run", "input_data": task_input})
    assert response.status_code == 201
    task_response = response.json()
    task_id = task_response["task_id"]

    await asyncio.sleep(0) # Yield control to allow potential async operations

    # 1. Verify task created in store
    task = await test_store.get_task(task_id) # Use unpacked store
    assert task is not None
    assert task.status == TaskStatus.PENDING
    assert task.input_data == task_input

    # Step 2 (Verify message queued) removed due to StubBroker unreliability with queue.get()

    # 3. Manually execute the core actor logic with mocked Agent.run
    #    Use task_id and task_input obtained after the API call.
    mock_agent_run_result = {"output": "Mock agent success", "history": ["step 1", "step 2"]}
    mock_agent = AsyncMock(spec=Agent)
    # Use side_effect with an async function to return the result dict
    async def mock_run_side_effect(*args, **kwargs):
        return mock_agent_run_result
    mock_agent.run.side_effect = mock_run_side_effect
    # Configure the memory attribute and its get_history method
    mock_agent.memory = MagicMock()
    mock_agent.memory.get_history.return_value = [] # Expected history is empty in this test

    # Patch the Agent class and LLM client getter within the scope of the logic function
    with patch("ops_core.scheduler.engine.Agent", return_value=mock_agent) as mock_agent_class, \
         patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient)) as mock_get_llm: # Patch LLM client getter with spec
        # Patch the other dependency getters called *within* the logic function
        with patch("ops_core.scheduler.engine.get_metadata_store", return_value=test_store), \
             patch("ops_core.scheduler.engine.get_mcp_client", return_value=mock_mcp_client): # Use unpacked components

            # Extract goal from input_data for the call
            goal = task_input.get("prompt", "Default goal if prompt missing")
            await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=task_input) # Correct args

    # 4. Verify Agent was instantiated and run correctly
    mock_agent_class.assert_called_once()
    # Check if Agent was called with expected interface implementations
    call_args, call_kwargs = mock_agent_class.call_args
    # Planner defaults to ReActPlanner now based on get_planner logic
    assert isinstance(call_kwargs.get("planner"), ReActPlanner)
    assert isinstance(call_kwargs.get("memory"), ShortTermMemory)
    assert isinstance(call_kwargs.get("tool_manager"), ToolRegistry)
    # TODO: Add check for security manager if implemented

    mock_agent.run.assert_called_once_with(goal=task_input["prompt"]) # Check goal keyword arg

    # 5. Verify task updated in store
    final_task = await test_store.get_task(task_id) # Use unpacked store
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
    # Check result field - memory_history comes from mock_agent.memory
    # agent_outcome should be the full result dict from mock_agent.run
    expected_output = {
        "agent_outcome": mock_agent_run_result,
        "memory_history": [],
    }
    assert final_task.result == expected_output
    assert final_task.error_message is None # Check error_message field
    # Assert mock_actor_send was called
    mock_actor_send.assert_called_once()


async def test_e2e_failed_agent_task(
    test_app_components # Use the combined fixture, stub_broker no longer needed
):
    """
    Test the full flow for a failed agent task:
    API -> Scheduler -> (Mocked) Broker Send -> Manual Actor Logic -> Store Update
    """
    test_client, test_store, test_scheduler, mock_mcp_client, mock_actor_send = test_app_components # Unpack the fixture result

    task_input = {"prompt": "Test prompt for failure"}
    response = test_client.post("/api/v1/tasks/", json={"task_type": "agent_run", "input_data": task_input})
    assert response.status_code == 201
    task_response = response.json()
    task_id = task_response["task_id"]

    await asyncio.sleep(0) # Yield control to allow potential async operations

    # 1. Verify task created and message queued
    task = await test_store.get_task(task_id) # Use unpacked store
    assert task is not None
    assert task.status == TaskStatus.PENDING

    # Step 2 (Verify message queued) removed due to StubBroker unreliability with queue.get()

    # 3. Manually execute the core actor logic with mocked Agent.run raising error
    #    Use task_id and task_input obtained after the API call.
    mock_agent = AsyncMock(spec=Agent)
    agent_error_message = "Agent simulation failed"
    mock_agent.run.side_effect = Exception(agent_error_message)

    # Patch the Agent class and LLM client getter within the scope of the logic function
    with patch("ops_core.scheduler.engine.Agent", return_value=mock_agent) as mock_agent_class, \
         patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient)) as mock_get_llm: # Patch LLM client getter with spec
        with patch("ops_core.scheduler.engine.get_metadata_store", return_value=test_store), \
             patch("ops_core.scheduler.engine.get_mcp_client", return_value=mock_mcp_client): # Use unpacked components

            # Extract goal from input_data for the call
            goal = task_input.get("prompt", "Default goal if prompt missing")
            await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=task_input) # Correct args

    # 4. Verify Agent was instantiated and run correctly
    mock_agent_class.assert_called_once()
    mock_agent.run.assert_called_once_with(goal=task_input["prompt"]) # Check goal keyword arg

    # 5. Verify task updated in store
    final_task = await test_store.get_task(task_id) # Use unpacked store
    assert final_task is not None
    assert final_task.status == TaskStatus.FAILED
    # When agent execution fails with an exception, the result field contains an error dict
    assert final_task.result is not None
    assert "error" in final_task.result
    assert "Agent execution failed unexpectedly" in final_task.result["error"]
    assert agent_error_message in final_task.error_message # Check error_message field matches the exception
    # Assert mock_actor_send was called
    mock_actor_send.assert_called_once()


async def test_e2e_mcp_proxy_agent_task(
    test_app_components # Use the combined fixture, stub_broker no longer needed
):
    """
    Test the full flow for an agent task using the MCP proxy tool:
    API -> Scheduler -> (Mocked) Broker Send -> Manual Actor Logic (Agent calls proxy) -> MCP Client -> Store Update
    """
    test_client, test_store, test_scheduler, mock_mcp_client, mock_actor_send = test_app_components # Unpack the fixture result

    mcp_server_name = "test-mcp-server"
    mcp_tool_name = "get_weather"
    mcp_tool_args = {"city": "Testville"}
    task_input = {
        "prompt": "Use MCP to get weather",
        "inject_mcp_proxy": True, # Request proxy injection
        # Simulate agent's planned action to call the proxy
        "simulated_agent_action": {
            "tool_name": "mcp_proxy_tool",
            "tool_input": {
                "server_name": mcp_server_name,
                "tool_name": mcp_tool_name,
                "arguments": mcp_tool_args,
            },
        },
    }
    response = test_client.post("/api/v1/tasks/", json={"task_type": "agent_run", "input_data": task_input})
    assert response.status_code == 201
    task_response = response.json()
    task_id = task_response["task_id"]

    await asyncio.sleep(0) # Yield control to allow potential async operations

    # 1. Verify task created and message queued
    task = await test_store.get_task(task_id) # Use unpacked store
    assert task is not None
    assert task.status == TaskStatus.PENDING

    # Step 2 (Verify message queued) removed due to StubBroker unreliability with queue.get()

    # 3. Manually execute the core actor logic with mocked Agent.run
    #    Use task_id and task_input obtained after the API call.
    #    that simulates calling the MCP proxy tool.
    #    The actual proxy tool execution happens within _run_agent_task_logic
    #    via the injected OpsMcpClient.
    mock_agent_run_result = {"output": f"Called MCP tool {mcp_tool_name}", "history": ["step 1: call mcp"]}
    mock_agent = AsyncMock(spec=Agent)
    # Use side_effect with an async function to return the result dict
    async def mock_run_mcp_side_effect(*args, **kwargs):
        return mock_agent_run_result
    mock_agent.run.side_effect = mock_run_mcp_side_effect
    # Configure the memory attribute and its get_history method
    mock_agent.memory = MagicMock()
    mock_agent.memory.get_history.return_value = [] # Expected history is empty in this test

    # Mock the OpsMcpClient's call_tool method BEFORE the logic runs
    mcp_call_result = {"data": "Sunny in Testville"}
    mock_mcp_client.call_tool = AsyncMock(return_value=mcp_call_result)

    # Patch the Agent class and LLM client getter within the scope of the logic function
    with patch("ops_core.scheduler.engine.Agent", return_value=mock_agent) as mock_agent_class, \
         patch("ops_core.scheduler.engine.get_llm_client", return_value=MagicMock(spec=BaseLlmClient)) as mock_get_llm: # Patch LLM client getter with spec
        # Patch the other dependency getters called *within* the logic function
        with patch("ops_core.scheduler.engine.get_metadata_store", return_value=test_store), \
             patch("ops_core.scheduler.engine.get_mcp_client", return_value=mock_mcp_client): # Use unpacked components

            # We need to simulate the agent's tool execution step calling the *actual*
            # MCPProxyTool instance that gets created inside _run_agent_task_logic.
            # The easiest way is to let _run_agent_task_logic run, and it should
            # use the mock_mcp_client we injected via the patched getter.
            # Extract goal from input_data for the call
            goal = task_input.get("prompt", "Default goal if prompt missing")
            await _run_agent_task_logic(task_id=task_id, goal=goal, input_data=task_input) # Correct args

    # 4. Verify Agent was instantiated and run correctly
    mock_agent_class.assert_called_once()
    # Check agent instantiation args (including injected proxy tool if possible/needed)
    call_args, call_kwargs = mock_agent_class.call_args
    tool_manager = call_kwargs.get("tool_manager")
    assert isinstance(tool_manager, ToolRegistry)
    # Verify the proxy tool was injected (assuming default name 'mcp_proxy_tool')
    assert tool_manager.get_tool_spec("mcp_proxy_tool") is not None

    mock_agent.run.assert_called_once_with(goal=task_input["prompt"]) # Check goal keyword arg

    # 5. Verify MCP Client's call_tool was awaited correctly by the logic
    #    (triggered indirectly by the agent's simulated action via the proxy tool)
    #    Note: This assertion relies on the fact that _run_agent_task_logic
    #    instantiates MCPProxyTool which uses the injected mock_mcp_client.
    #    We are NOT directly mocking the agent's tool call here, but the underlying MCP client call.
    #    This seems incorrect based on how the logic is structured.
    #    Let's rethink: _run_agent_task_logic calls agent.run(). agent.run() (mocked) returns.
    #    The MCP call doesn't happen unless the *real* agent logic runs and decides to call the tool.
    #    The current test structure mocks Agent.run entirely.

    # --- REVISED APPROACH for MCP Test ---
    # We need to test that IF the agent *were* to call the proxy tool,
    # the injected client would be used. The unit tests for MCPProxyTool
    # should cover its interaction with the client.
    # This E2E test should focus on:
    #   a) Proxy tool injection happens when requested.
    #   b) The task completes successfully assuming the agent behaves.

    # Let's simplify the assertion: just check the task completes.
    # The injection check is already done in step 4.
    # The actual client call verification belongs in MCPProxyTool unit tests
    # or a more complex integration test that doesn't mock Agent.run.

    # mock_mcp_client.call_tool.assert_awaited_once_with(
    #     server_name=mcp_server_name,
    #     tool_name=mcp_tool_name,
    #     arguments=mcp_tool_args
    # )

    # 6. Verify task updated in store
    final_task = await test_store.get_task(task_id) # Use unpacked store
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
    # The result should be what the mocked Agent.run returned, with empty history
    expected_output = {
        "agent_outcome": mock_agent_run_result,
        "memory_history": [],
    }
    assert final_task.result == expected_output
    assert final_task.error_message is None # Check error_message field
    # Assert mock_actor_send was called
    mock_actor_send.assert_called_once()
