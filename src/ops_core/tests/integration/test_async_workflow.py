"""
Integration tests verifying API -> Scheduler -> Actor Dispatch.
Does NOT simulate actor execution. Relies on unit tests for actor logic.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import uuid

from fastapi.testclient import TestClient
# Explicitly import required gRPC submodules
from grpc import aio as grpc_aio

# Import project components
from src.ops_core.main import app as fastapi_app
from src.ops_core.scheduler.engine import InMemoryScheduler
from src.ops_core.metadata.store import InMemoryMetadataStore # Using InMemory for these tests
from src.ops_core.mcp_client.client import OpsMcpClient
from src.ops_core.models.tasks import Task, TaskStatus
from src.ops_core.api.v1.endpoints import tasks as tasks_api

# Import dependencies container
from src.ops_core.dependencies import deps

from src.ops_core.grpc_internal.task_servicer import TaskServicer
from src.ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc
# Only need the actor object to patch its send method
from src.ops_core.scheduler.engine import execute_agent_task_actor


# --- Fixtures ---

@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_deps():
    """Resets dependencies before/after each test, handling potential non-existence."""
    # Reset dependencies container safely
    original_client = getattr(deps, 'mcp_client', None)
    original_store = getattr(deps, 'metadata_store', None) # Use getattr with default None
    deps.mcp_client = None
    deps.metadata_store = None # Ensure it's None before test runs
    yield
    # Restore original deps only if they existed
    if original_client is not None:
        deps.mcp_client = original_client
    if original_store is not None:
        deps.metadata_store = original_store # Restore only if it existed


@pytest_asyncio.fixture(scope="function")
async def test_metadata_store() -> InMemoryMetadataStore:
    """Provides a clean InMemoryMetadataStore for each test."""
    return InMemoryMetadataStore()

@pytest_asyncio.fixture
async def mock_mcp_client() -> MagicMock:
    """Provides a mocked OpsMcpClient."""
    client = MagicMock(spec=OpsMcpClient)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()
    client.call_tool = AsyncMock()
    return client

@pytest_asyncio.fixture
async def test_scheduler(
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock
) -> InMemoryScheduler:
    """Provides an InMemoryScheduler with test dependencies."""
    # Set dependencies in the container for the scheduler instance if needed
    deps.metadata_store = test_metadata_store
    deps.mcp_client = mock_mcp_client
    scheduler = InMemoryScheduler(
        metadata_store=test_metadata_store,
        mcp_client=mock_mcp_client # Pass mock client
    )
    return scheduler

@pytest.fixture
def test_client(
    test_scheduler: InMemoryScheduler,
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock
) -> TestClient:
    """Provides a FastAPI TestClient with overridden dependencies."""
    from src.ops_core.dependencies import get_metadata_store as api_get_store
    from src.ops_core.dependencies import get_mcp_client as api_get_client

    # Ensure deps are set for the API context *before* creating TestClient
    # This allows TestClient's context manager to potentially run lifespan,
    # but our overrides will take precedence for the actual test execution.
    deps.metadata_store = test_metadata_store
    deps.mcp_client = mock_mcp_client

    # Set dependency overrides
    fastapi_app.dependency_overrides[api_get_store] = lambda: test_metadata_store
    fastapi_app.dependency_overrides[api_get_client] = lambda: mock_mcp_client
    fastapi_app.dependency_overrides[tasks_api.get_scheduler] = lambda: test_scheduler

    # Create the TestClient *after* setting overrides
    client = TestClient(fastapi_app)
    yield client # Yield the client for the test

    # Clean up overrides after the test
    fastapi_app.dependency_overrides = {}


@pytest_asyncio.fixture(scope="function")
async def grpc_server(test_scheduler: InMemoryScheduler, test_metadata_store: InMemoryMetadataStore, mock_mcp_client: MagicMock):
    """Starts an in-process gRPC server for testing."""
    server = grpc_aio.server()
    # Set dependencies in the global container for the servicer
    deps.metadata_store = test_metadata_store
    deps.mcp_client = mock_mcp_client
    tasks_pb2_grpc.add_TaskServiceServicer_to_server(
        # Pass both scheduler and metadata_store to TaskServicer
        TaskServicer(scheduler=test_scheduler, metadata_store=test_metadata_store), server
    )
    port = server.add_insecure_port("[::]:0")
    await server.start()
    yield f"localhost:{port}"
    await server.stop(grace=0.1)


@pytest_asyncio.fixture(scope="function")
async def grpc_client(grpc_server: str):
    """Provides a gRPC client connected to the test server."""
    async with grpc_aio.insecure_channel(grpc_server) as channel:
        yield tasks_pb2_grpc.TaskServiceStub(channel)


# --- Test Cases ---

@pytest.mark.asyncio
async def test_rest_api_dispatches_agent_task(
    test_client: TestClient,
    test_metadata_store: InMemoryMetadataStore,
):
    """Verify REST API creates task and calls actor.send()."""
    task_data = {"task_type": "agent_run", "input_data": {"goal": "async rest goal"}}
    task_id = None

    # Patch the actor's send method for this test scope
    with patch('src.ops_core.scheduler.engine.execute_agent_task_actor.send') as mock_actor_send:
        response = test_client.post("/api/v1/tasks/", json=task_data)

    # --- Assertions ---
    assert response.status_code == 201 # Check API response first
    response_json = response.json()
    task_id = response_json["task_id"]
    assert response_json["status"] == TaskStatus.PENDING.value

    # Verify task created in store
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.input_data == task_data["input_data"]

    # Verify actor send was called correctly
    mock_actor_send.assert_called_once()
    call_args, call_kwargs = mock_actor_send.call_args
    assert call_kwargs.get('task_id') == task_id
    assert call_kwargs.get('goal') == task_data["input_data"]["goal"]
    assert call_kwargs.get('input_data') == task_data["input_data"]


@pytest.mark.asyncio
async def test_grpc_api_dispatches_agent_task(
    grpc_client: tasks_pb2_grpc.TaskServiceStub,
    test_metadata_store: InMemoryMetadataStore,
):
    """Verify gRPC API creates task and calls actor.send()."""
    input_dict = {"goal": "async grpc goal"}
    input_struct = tasks_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    input_struct.update(input_dict)
    request = tasks_pb2.CreateTaskRequest(
        task_type="agent_run", input_data=input_struct
    )
    task_id = None

    # Patch the actor's send method for this test scope
    with patch('src.ops_core.scheduler.engine.execute_agent_task_actor.send') as mock_actor_send:
        response = await grpc_client.CreateTask(request)

    # --- Assertions ---
    assert response.task.task_type == "agent_run" # Check gRPC response first
    assert response.task.status == tasks_pb2.PENDING
    task_id = response.task.task_id

    # Verify task created in store
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.input_data == input_dict

    # Verify actor send was called correctly
    mock_actor_send.assert_called_once()
    call_args, call_kwargs = mock_actor_send.call_args
    assert call_kwargs.get('task_id') == task_id
    assert call_kwargs.get('goal') == input_dict["goal"]
    assert call_kwargs.get('input_data') == input_dict


@pytest.mark.asyncio
async def test_rest_api_dispatches_failure_task( # Renamed for clarity
    test_client: TestClient,
    test_metadata_store: InMemoryMetadataStore,
):
    """Verify REST API creates task and calls actor.send() even if actor will fail."""
    task_data = {"task_type": "agent_run", "input_data": {"goal": "async failure goal"}}
    task_id = None

    # Patch the actor's send method for this test scope
    with patch('src.ops_core.scheduler.engine.execute_agent_task_actor.send') as mock_actor_send:
        response = test_client.post("/api/v1/tasks/", json=task_data)

    # --- Assertions ---
    assert response.status_code == 201 # Check API response first
    task_id = response.json()["task_id"]

    # Verify task created
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING
    assert stored_task.input_data == task_data["input_data"]

    # Verify actor send was called correctly
    mock_actor_send.assert_called_once()
    call_args, call_kwargs = mock_actor_send.call_args
    assert call_kwargs.get('task_id') == task_id
    assert call_kwargs.get('goal') == task_data["input_data"]["goal"]
    assert call_kwargs.get('input_data') == task_data["input_data"]
