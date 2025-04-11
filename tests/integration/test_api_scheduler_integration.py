"""
Integration tests for API endpoints interacting with the Scheduler.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import httpx # Import httpx

from fastapi import FastAPI
# Remove TestClient import
# from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# Explicitly import required gRPC submodules
from grpc import aio as grpc_aio

# Import project components
from ops_core.main import app as fastapi_app # Import the FastAPI app instance
from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.sql_store import SqlMetadataStore # Import real store
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.models.tasks import Task, TaskStatus # Import Task model
# Import dependency getters
from ops_core.dependencies import get_scheduler, get_metadata_store, get_db_session, get_mcp_client
from ops_core.grpc_internal.task_servicer import TaskServicer
from ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc
from ops_core.config.loader import McpConfig # Import for mocking

# --- Fixtures ---

# Remove mock_metadata_store fixture

@pytest_asyncio.fixture
async def mock_mcp_client() -> MagicMock:
    """Provides a mocked OpsMcpClient."""
    client = MagicMock(spec=OpsMcpClient)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()
    client.call_tool = AsyncMock()
    return client

@pytest_asyncio.fixture
async def mock_scheduler( # Renaming to real_scheduler_mock_client might be clearer, but keep name for now
    db_session: AsyncSession, # Inject db_session
    mock_mcp_client: MagicMock
) -> InMemoryScheduler:
    """Provides an InMemoryScheduler with a real SqlMetadataStore and mocked MCP client."""
    # Create real store instance, passing the test session
    sql_store = SqlMetadataStore(session=db_session) # Pass the session
    scheduler = InMemoryScheduler(
        metadata_store=sql_store, # Use real store
        mcp_client=mock_mcp_client
    )
    # No longer mocking _execute_agent_task or _process_tasks here,
    # as execution is now handled by Dramatiq actors.
    # We will patch the actor's send method in specific tests.
    # The store is already set correctly in __init__
    return scheduler

@pytest_asyncio.fixture # Add async fixture decorator
async def test_client( # Change to async def
    db_session: AsyncSession, # Inject db_session
    mock_scheduler: InMemoryScheduler, # Keep using the updated mock_scheduler fixture
    mock_mcp_client: MagicMock
) -> httpx.AsyncClient: # Change return type hint
    """Provides an httpx.AsyncClient with overridden dependencies (real store via db_session)."""
    # Override get_db_session to provide the test session
    # Need to import the original functions to override them
    from ops_core.dependencies import get_db_session as original_get_db_session
    from ops_core.dependencies import get_scheduler as original_get_scheduler
    from ops_core.dependencies import get_mcp_client as original_get_mcp_client
    from ops_core.dependencies import get_metadata_store as original_get_metadata_store # Import original store getter

    fastapi_app.dependency_overrides[original_get_db_session] = lambda: db_session
    # Override scheduler and mcp client
    fastapi_app.dependency_overrides[original_get_scheduler] = lambda: mock_scheduler
    fastapi_app.dependency_overrides[original_get_mcp_client] = lambda: mock_mcp_client
    # Explicitly override get_metadata_store to use the test session
    # This ensures the store used by API endpoints gets the correct session
    # Note: We need to create the store instance here to capture db_session
    sql_store_for_api = SqlMetadataStore(session=db_session)
    fastapi_app.dependency_overrides[original_get_metadata_store] = lambda: sql_store_for_api

    # Use httpx.AsyncClient with ASGITransport
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client # Use yield to ensure proper teardown if needed

    # Clean up overrides after test (happens automatically when fixture scope ends)
    fastapi_app.dependency_overrides = {}


@pytest_asyncio.fixture(scope="function")
async def grpc_server(
    mock_scheduler: InMemoryScheduler, # Keep mock scheduler
    db_session: AsyncSession # Inject db_session
):
    """Starts an in-process gRPC server for testing with real store."""
    # Create real store instance, passing the test session
    sql_store = SqlMetadataStore(session=db_session) # Pass the session
    server = grpc_aio.server()
    tasks_pb2_grpc.add_TaskServiceServicer_to_server(
        # Inject mock scheduler and store (with correct session) into servicer
        TaskServicer(scheduler=mock_scheduler, metadata_store=sql_store),
        server
    )
    port = server.add_insecure_port("[::]:0") # Use random available port
    await server.start()
    yield f"localhost:{port}" # Return the address
    await server.stop(grace=0.1)


@pytest_asyncio.fixture(scope="function")
async def grpc_client(grpc_server: str):
    """Provides a gRPC client connected to the test server."""
    async with grpc_aio.insecure_channel(grpc_server) as channel:
        yield tasks_pb2_grpc.TaskServiceStub(channel)


# --- Test Cases ---

# Add missing asyncio marker
@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch actor for submit tests
async def test_rest_api_submit_non_agent_task(
    mock_actor: MagicMock, # Add mock actor arg
    test_client: httpx.AsyncClient, # Update type hint
    mock_scheduler: InMemoryScheduler, # Keep mock scheduler
    db_session: AsyncSession # Inject session for verification
    # Removed mock_metadata_store argument
):
    """Verify REST API task submission calls scheduler and updates store (DB)."""
    task_data = {"task_type": "simple_test", "input_data": {"value": 123}}

    # Mock the scheduler's submit_task to check it's called correctly
    mock_scheduler.submit_task = AsyncMock(wraps=mock_scheduler.submit_task)

    # Use await with httpx.AsyncClient
    response = await test_client.post("/api/v1/tasks/", json=task_data)

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["task_type"] == "simple_test"
    assert response_json["status"] == TaskStatus.PENDING.value # Compare with enum value
    assert "task_id" in response_json
    task_id = response_json["task_id"]

    # Check scheduler was called
    mock_scheduler.submit_task.assert_awaited_once()
    call_args = mock_scheduler.submit_task.call_args.kwargs
    assert call_args['name'] == "API Task - simple_test"
    assert call_args['task_type'] == "simple_test"
    assert call_args['input_data'] == {"value": 123}

    # Check task exists in DB via the real store used by the scheduler
    # Note: We access the store via the scheduler fixture instance
    stored_task = await mock_scheduler.metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.task_id == task_id
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.task_type == "simple_test"

    # Ensure Dramatiq actor send was NOT called for non-agent task
    mock_actor.send.assert_not_called()


@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch actor for submit tests
async def test_rest_api_submit_agent_task(
    mock_actor: MagicMock, # Add mock actor arg
    test_client: httpx.AsyncClient, # Update type hint
    mock_scheduler: InMemoryScheduler, # Keep mock scheduler
    db_session: AsyncSession, # Inject session for verification
    # Removed mock_metadata_store argument
    mocker # Add mocker fixture
):
    """Verify REST API agent task submission calls scheduler which calls actor send (DB)."""
    # Patch MCP config loading locally for this test
    mocker.patch(
        "ops_core.config.loader.get_resolved_mcp_config",
        return_value=McpConfig(servers={}),
    )
    task_data = {"task_type": "agent_run", "input_data": {"goal": "rest agent goal"}}

    # Mock the scheduler's submit_task to check it's called correctly
    # Use the real submit_task from the fixture
    # mock_scheduler.submit_task = AsyncMock(wraps=mock_scheduler.submit_task)

    # Mock Agent being available within the scheduler's context for this test
    with patch('ops_core.scheduler.engine.Agent', new=MagicMock()):
        # Use await with httpx.AsyncClient
        response = await test_client.post("/api/v1/tasks/", json=task_data)

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["task_type"] == "agent_run"
    assert response_json["status"] == TaskStatus.PENDING.value
    task_id = response_json["task_id"]

    # Check task exists in DB via the real store used by the scheduler
    stored_task = await mock_scheduler.metadata_store.get_task(task_id)
    assert stored_task is not None

    # Ensure Dramatiq actor send WAS called by the scheduler's submit_task
    mock_actor.send.assert_called_once_with(
        task_id=task_id,
        goal=task_data["input_data"].get("goal", "No goal specified"),
        input_data=task_data["input_data"]
    )


@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch actor for submit tests
async def test_grpc_api_submit_non_agent_task(
    mock_actor: MagicMock, # Add mock actor arg
    grpc_client: tasks_pb2_grpc.TaskServiceStub, # Uses updated fixture
    mock_scheduler: InMemoryScheduler, # Keep mock scheduler
    db_session: AsyncSession # Inject session for verification
    # Removed mock_metadata_store argument
):
    """Verify gRPC API task submission calls scheduler and updates store (DB)."""
    input_struct = tasks_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    input_struct.update({"value": 456})
    request = tasks_pb2.CreateTaskRequest(
        task_type="grpc_test", input_data=input_struct
    )

    # Mock the scheduler's submit_task to check it's called correctly
    mock_scheduler.submit_task = AsyncMock(wraps=mock_scheduler.submit_task)

    response = await grpc_client.CreateTask(request)

    assert response.task.task_type == "grpc_test"
    assert response.task.status == tasks_pb2.PENDING
    assert response.task.task_id is not None
    task_id = response.task.task_id

    # Check scheduler was called
    mock_scheduler.submit_task.assert_awaited_once()
    call_args = mock_scheduler.submit_task.call_args.kwargs
    assert call_args['name'] == "gRPC Task - grpc_test"
    assert call_args['task_type'] == "grpc_test"
    assert call_args['input_data'] == {"value": 456}

    # Check task exists in DB via the real store used by the scheduler
    stored_task = await mock_scheduler.metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.task_id == task_id
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.task_type == "grpc_test"

    # Ensure Dramatiq actor send was NOT called for non-agent task
    mock_actor.send.assert_not_called()


@pytest.mark.asyncio
@patch('ops_core.scheduler.engine.execute_agent_task_actor') # Patch actor for submit tests
async def test_grpc_api_submit_agent_task(
    mock_actor: MagicMock, # Add mock actor arg
    grpc_client: tasks_pb2_grpc.TaskServiceStub, # Uses updated fixture
    mock_scheduler: InMemoryScheduler, # Keep mock scheduler
    db_session: AsyncSession, # Inject session for verification
    # Removed mock_metadata_store argument
    mocker # Add mocker fixture
):
    """Verify gRPC API agent task submission calls scheduler which calls actor send (DB)."""
    # Patch MCP config loading locally for this test
    mocker.patch(
        "ops_core.config.loader.get_resolved_mcp_config",
        return_value=McpConfig(servers={}),
    )
    input_dict = {"goal": "grpc agent goal"}
    input_struct = tasks_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    input_struct.update(input_dict)
    request = tasks_pb2.CreateTaskRequest(
        task_type="agent_run", input_data=input_struct
    )

    # Mock Agent being available within the scheduler's context for this test
    with patch('ops_core.scheduler.engine.Agent', new=MagicMock()):
        response = await grpc_client.CreateTask(request)

    assert response.task.task_type == "agent_run"
    assert response.task.status == tasks_pb2.PENDING
    task_id = response.task.task_id

    # Check task exists in DB via the real store used by the scheduler
    stored_task = await mock_scheduler.metadata_store.get_task(task_id)
    assert stored_task is not None

    # Ensure Dramatiq actor send WAS called by the scheduler's submit_task
    mock_actor.send.assert_called_once_with(
        task_id=task_id,
        goal=input_dict.get("goal", "No goal specified"),
        input_data=input_dict
    )


# Removed test_scheduler_triggers_agent_execution as it tested the old
# direct asyncio.create_task behavior which is replaced by Dramatiq actor calls.
