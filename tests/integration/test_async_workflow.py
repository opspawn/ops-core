# Integration tests for the asynchronous agent task workflow

import asyncio
from unittest.mock import patch, MagicMock

import pytest

from fastapi.testclient import TestClient

from ops_core.models.tasks import TaskStatus
from ops_core.config.loader import McpConfig # Import for mocking

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


# Note: We need a fixture similar to test_e2e_workflow's test_app_components
# to provide the TestClient and mocked dependencies. Let's define it locally for now.
# Ideally, this could be moved to conftest.py if used by multiple integration test files.

@pytest.fixture(scope="function")
def test_app_components_async(mock_metadata_store, mock_mcp_client, stub_broker, mocker): # Added stub_broker
    """
    Creates FastAPI TestClient, InMemoryMetadataStore, and mocked OpsMcpClient
    with dependencies correctly overridden for async workflow integration testing.
    Uses the stub_broker fixture.
    Yields the client, store, scheduler, mcp_client, and stub_broker.
    """
    from ops_core.main import app as fastapi_app # Import locally to avoid top-level side effects
    from ops_core.scheduler.engine import InMemoryScheduler
    from ops_core.api.v1.endpoints import tasks as tasks_api

    test_store = mock_metadata_store # Use the fixture directly
    test_scheduler = InMemoryScheduler(metadata_store=test_store, mcp_client=mock_mcp_client)

    # Override dependencies
    fastapi_app.dependency_overrides[tasks_api.get_metadata_store] = lambda: test_store
    fastapi_app.dependency_overrides[tasks_api.get_mcp_client] = lambda: mock_mcp_client
    fastapi_app.dependency_overrides[tasks_api.get_scheduler] = lambda: test_scheduler

    # Patch the config loader and ensure dramatiq uses the stub broker
    with patch("ops_core.mcp_client.client.get_resolved_mcp_config", return_value=McpConfig(servers={})), \
         patch("dramatiq.set_broker"), \
         patch("dramatiq.get_broker", return_value=stub_broker):
        # Set broker explicitly for the current context as well
        from dramatiq import set_broker
        set_broker(stub_broker)
        test_client = TestClient(fastapi_app)
        yield test_client, test_store, test_scheduler, mock_mcp_client, stub_broker # Yield stub_broker instead of mock_actor_send

    # Cleanup overrides
    fastapi_app.dependency_overrides = {}


async def test_rest_api_triggers_async_actor_send(
    test_app_components_async, # Use the local fixture
    mocker # Add mocker for patching Agent
):
    """
    Verify submitting an agent_run task via REST API triggers the actor's send method.
    (Relies on dramatiq using the stub_broker provided by the fixture).
    """
    test_client, test_store, test_scheduler, mock_mcp_client, stub_broker = test_app_components_async

    task_data = {"task_type": "agent_run", "input_data": {"goal": "async workflow test"}}

    # Mock Agent class within the scheduler engine's scope to avoid instantiation errors
    # during the submit_task call, as we only care about the send call here.
    # Note: The actual send call is still commented out in engine.py at this stage,
    # so this test *should fail* until Step 3. We add it now to prepare.
    # UPDATE: No, the test should pass because we are patching the send method itself.
    with patch('ops_core.scheduler.engine.Agent', new=MagicMock()):
        response = test_client.post("/api/v1/tasks/", json=task_data)

    assert response.status_code == 201
    response_json = response.json()
    task_id = response_json["task_id"]

    # Allow event loop to process potential async operations
    await asyncio.sleep(0)

    # Verify task created in store
    stored_task = await test_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.task_type == "agent_run"

    # Verify a message was enqueued on the stub broker
    assert not stub_broker.is_empty(execute_agent_task_actor.queue_name)
    queued_message = stub_broker.get_message(execute_agent_task_actor.queue_name)
    assert queued_message is not None
    assert queued_message.message_id is not None
    assert queued_message.args == [task_id, task_data["input_data"].get("goal", "No goal specified"), task_data["input_data"]]


async def test_full_async_workflow_success(
    test_app_components_async, # Use the local fixture
    stub_worker, # Use worker fixture from conftest
    mocker # Use mocker for patching
):
    """
    Test the full async workflow: API -> StubBroker -> StubWorker -> Actor Logic (Mocked Agent) -> Store Update
    """
    test_client, test_store, test_scheduler, mock_mcp_client, stub_broker = test_app_components_async

    # --- Arrange Actor Logic Mocks ---
    agent_final_result = {"status": "Success", "output": "Full workflow success!"}
    agent_history = ["Full Step 1"]

    # Patch dependency getters used within _run_agent_task_logic
    mocker.patch('ops_core.dependencies.get_metadata_store', return_value=test_store) # Use the test store
    mocker.patch('ops_core.dependencies.get_mcp_client', return_value=mock_mcp_client)

    # Mock Agent.run and memory.get_context
    mock_agent_run = mocker.patch('ops_core.scheduler.engine.Agent.run', new_callable=AsyncMock, return_value=agent_final_result)
    mock_get_context = mocker.patch('agentkit.memory.short_term.ShortTermMemory.get_context', new_callable=AsyncMock, return_value=agent_history)

    # Patch other potential dependencies inside the logic if needed
    mocker.patch("ops_core.scheduler.engine.get_llm_client")
    mocker.patch("ops_core.scheduler.engine.get_planner")
    mocker.patch("ops_core.scheduler.engine.ToolRegistry")
    mocker.patch("ops_core.scheduler.engine.MCPProxyTool")

    # --- Act ---
    task_data = {"task_type": "agent_run", "input_data": {"goal": "full async goal"}}
    response = test_client.post("/api/v1/tasks/", json=task_data)
    assert response.status_code == 201
    task_id = response.json()["task_id"]

    # Verify task initially pending
    task_before = await test_store.get_task(task_id)
    assert task_before is not None
    assert task_before.status == TaskStatus.PENDING

    # Start the worker and process the message
    stub_worker.start()
    try:
        # Use fail_fast=True based on documentation recommendation
        stub_broker.join(execute_agent_task_actor.queue_name, fail_fast=True, timeout=5000) # Added timeout
    finally:
        stub_worker.stop() # Ensure worker stops even if join fails

    # --- Assert ---
    # Verify Agent.run was called
    mock_agent_run.assert_awaited_once_with(goal=task_data["input_data"]["goal"])
    mock_get_context.assert_awaited_once()

    # Verify final task status and result in store
    final_task = await test_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.result is not None
    assert final_task.result.get("agent_outcome") == agent_final_result
    assert final_task.result.get("memory_history") == agent_history
    assert final_task.error_message is None


# Keep the placeholder for now, can remove later
def test_placeholder():
    """Placeholder test to ensure the file is picked up."""
    assert True
