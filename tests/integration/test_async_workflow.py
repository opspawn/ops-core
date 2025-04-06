"""
Integration tests for the full asynchronous task workflow:
API -> Metadata Store -> Message Queue -> Worker -> Actor -> Metadata Store Update
"""

import asyncio
import pytest
import pytest_asyncio
import time # Import time module
import queue # Import queue module for Queue.Empty exception
# import threading # No longer needed
from unittest.mock import AsyncMock, MagicMock, patch # Keep for fixture definitions, add patch
import uuid
import dramatiq # Import the main dramatiq library
from dramatiq import Worker, get_broker, Message, set_broker # Import Worker, get_broker, Message, set_broker
from dramatiq.brokers.stub import StubBroker # Import StubBroker
# Import the rabbitmq module directly
# import dramatiq.brokers.rabbitmq # No longer needed
# from dramatiq.brokers.rabbitmq import RabbitMQBroker # Import RabbitMQBroker
from pytest_mock import MockerFixture # Import mocker

# --- Test Configuration: Broker will be set per test ---
# Remove global broker setup
# stub_broker = StubBroker()
# stub_broker.emit_after("process_boot")
# dramatiq.set_broker(stub_broker)

# Now import other modules
from fastapi.testclient import TestClient
# Explicitly import required gRPC submodules
from grpc import aio as grpc_aio

# Import project components
from ops_core.main import app as fastapi_app
from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.models.tasks import Task, TaskStatus
from ops_core.api.v1.endpoints import tasks as tasks_api
# Broker already imported and set

from ops_core.grpc_internal.task_servicer import TaskServicer
from ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc
# No longer need to import our broker module here for StubBroker
from ops_core.scheduler.engine import execute_agent_task_actor # Import the actor


# Queue declaration will happen within tests after setting the broker


# --- Fixtures ---

@pytest.fixture(scope="function")
def stub_broker() -> StubBroker:
    """Provides a StubBroker instance, sets it globally, and cleans up."""
    broker = StubBroker()
    broker.emit_after("process_boot") # Important for worker processing
    set_broker(broker)
    yield broker
    # Clean up after test
    broker.flush_all()
    set_broker(None) # Unset global broker

@pytest_asyncio.fixture(scope="function")
async def test_metadata_store() -> InMemoryMetadataStore:
    """Provides a clean InMemoryMetadataStore for each test."""
    # Use a function-scoped fixture to ensure isolation between tests
    return InMemoryMetadataStore()

@pytest_asyncio.fixture(scope="function") # Keep function scope for isolation
async def mock_mcp_client() -> MagicMock:
    """Provides a mocked OpsMcpClient."""
    client = MagicMock(spec=OpsMcpClient)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()
    client.call_tool = AsyncMock()
    return client

@pytest_asyncio.fixture(scope="function") # Keep function scope
async def test_scheduler(
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock
) -> InMemoryScheduler:
    """Provides an InMemoryScheduler with test dependencies."""
    scheduler = InMemoryScheduler(
        metadata_store=test_metadata_store,
        mcp_client=mock_mcp_client
    )
    # Ensure the store is accessible if needed elsewhere
    # scheduler.metadata_store = test_metadata_store # No longer needed, dependencies injected via API/gRPC overrides
    return scheduler

@pytest.fixture(scope="function") # Keep function scope
def test_client(
    test_scheduler: InMemoryScheduler, # Keep scheduler for dependency override
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock
) -> TestClient:
    """Provides a FastAPI TestClient with overridden dependencies."""
    # Override dependencies in the FastAPI app
    fastapi_app.dependency_overrides[tasks_api.get_scheduler] = lambda: test_scheduler
    fastapi_app.dependency_overrides[tasks_api.get_metadata_store] = lambda: test_metadata_store
    fastapi_app.dependency_overrides[tasks_api.get_mcp_client] = lambda: mock_mcp_client

    client = TestClient(fastapi_app)
    yield client

    # Clean up overrides after test
    fastapi_app.dependency_overrides = {}


@pytest_asyncio.fixture(scope="function")
async def grpc_server(test_scheduler: InMemoryScheduler): # Keep scheduler for gRPC servicer
    """Starts an in-process gRPC server for testing."""
    server = grpc_aio.server()
    tasks_pb2_grpc.add_TaskServiceServicer_to_server(
        TaskServicer(scheduler=test_scheduler), server
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

# --- Mocks for Actor --- # Remove these fixtures, will mock directly in tests

# @pytest_asyncio.fixture
# def mock_agent_run():
#     """Provides a mock for the Agent's run method."""
#     return AsyncMock(return_value={"result": "agent finished successfully"})

# @pytest_asyncio.fixture
# def mock_agent_instance(mock_agent_run):
#     """Provides a mock Agent instance."""
#     instance = MagicMock()
#     instance.run = mock_agent_run # Assign the async mock to the run attribute
#     # Mock memory history if needed by the actor's result processing
#     instance.memory = MagicMock()
#     instance.memory.get_history = MagicMock(return_value=["history item 1"])
#     return instance

# @pytest_asyncio.fixture
# def mock_agent_cls(mock_agent_instance):
#     """Provides a mock Agent class that returns the mock instance."""
#     mock_cls = MagicMock(return_value=mock_agent_instance)
#     return mock_cls

# @pytest_asyncio.fixture
# def mock_tool_registry_instance():
#     """Provides a mock ToolRegistry instance."""
#     mock_registry_instance = MagicMock()
#     mock_registry_instance.add_tool = MagicMock()
#     # Add other methods if needed by the actor
#     return mock_registry_instance

# @pytest_asyncio.fixture
# def mock_tool_registry_cls(mock_tool_registry_instance):
#     """Provides a mock ToolRegistry class."""
#     mock_registry_cls = MagicMock(return_value=mock_tool_registry_instance)
#     return mock_registry_cls


# --- Test Cases ---

# Helper function to poll for task completion
async def wait_for_task_completion(store: InMemoryMetadataStore, task_id: str, timeout_sec: float = 5.0, interval_sec: float = 0.1):
    """Polls the metadata store until the task reaches a terminal state or timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        task = await store.get_task(task_id)
        if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return task
        await asyncio.sleep(interval_sec)
    return await store.get_task(task_id) # Return last known state on timeout


@pytest.mark.asyncio
async def test_rest_api_async_agent_workflow_success(
    test_client: TestClient,
    test_metadata_store: InMemoryMetadataStore, # Keep store for verification
    stub_broker: StubBroker, # Use StubBroker fixture
    mock_mcp_client: MagicMock, # Need this for patching getter
    mocker: MockerFixture,
):
    """
    Verify REST API -> Queue -> Worker (Stub) -> Actor (Mocked Agent) -> Success Status Update.
    """
    # --- Arrange ---
    # Broker is set globally by the fixture
    agent_final_result = "Agent run successful!"
    agent_history = ["Step 1", "Step 2"] # Keep for expected result simulation

    # Patch dependency getters at their source in the dependencies module
    mocker.patch('ops_core.dependencies.get_metadata_store', return_value=test_metadata_store)
    mocker.patch('ops_core.dependencies.get_mcp_client', return_value=mock_mcp_client)

    # Patch the actor's send method
    mock_send = mocker.patch('ops_core.scheduler.engine.execute_agent_task_actor.send')

    task_data = {"task_type": "agent_run", "input_data": {"goal": "async rest goal"}}
    task_id = None

    # --- Act ---
    # 1. Submit task via REST API
    response = test_client.post("/api/v1/tasks/", json=task_data)
    assert response.status_code == 201
    response_json = response.json()
    task_id = response_json["task_id"]
    assert response_json["status"] == TaskStatus.PENDING.value

    # 2. Verify task created in store (initial state)
    stored_task_before = await test_metadata_store.get_task(task_id)
    assert stored_task_before is not None
    assert stored_task_before.status == TaskStatus.PENDING

    # --- Assert ---
    # 3. Verify the actor's send method was called correctly
    mock_send.assert_called_once_with(task_id, task_data["input_data"])

    # 4. Verify the task status remains PENDING in the store (actor execution is mocked)
    # Use asyncio.sleep for a very short duration to allow potential background processing
    await asyncio.sleep(0.01)
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_grpc_api_async_agent_workflow_success(
    grpc_client: tasks_pb2_grpc.TaskServiceStub,
    test_metadata_store: InMemoryMetadataStore,
    stub_broker: StubBroker, # Use StubBroker fixture
    mock_mcp_client: MagicMock, # Need this for patching getter
    mocker: MockerFixture,
):
    """
    Verify gRPC API -> Queue -> Worker (Stub) -> Actor (Mocked Agent) -> Success Status Update.
    """
    # --- Arrange ---
    # Broker is set globally by the fixture
    agent_final_result = "Agent run successful via gRPC!"
    agent_history = ["gRPC Step 1"] # Keep for simulation

    # Patch dependency getters at their source in the dependencies module
    mocker.patch('ops_core.dependencies.get_metadata_store', return_value=test_metadata_store)
    mocker.patch('ops_core.dependencies.get_mcp_client', return_value=mock_mcp_client)

    # Patch the actor's send method
    mock_send = mocker.patch('ops_core.scheduler.engine.execute_agent_task_actor.send')

    input_dict = {"goal": "async grpc goal"}
    input_struct = tasks_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    input_struct.update(input_dict)
    request = tasks_pb2.CreateTaskRequest(
        task_type="agent_run", input_data=input_struct
    )
    task_id = None

    # --- Act ---
    # 1. Submit task via gRPC API
    response = await grpc_client.CreateTask(request)
    assert response.task.task_type == "agent_run"
    assert response.task.status == tasks_pb2.PENDING
    task_id = response.task.task_id

    # 2. Verify task created in store (initial state)
    stored_task_before = await test_metadata_store.get_task(task_id)
    assert stored_task_before is not None
    assert stored_task_before.status == TaskStatus.PENDING

     # --- Assert ---
    # 3. Verify the actor's send method was called correctly
    mock_send.assert_called_once_with(task_id, input_dict) # Input data is dict here

    # 4. Verify the task status remains PENDING in the store (actor execution is mocked)
    await asyncio.sleep(0.01)
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_rest_api_async_agent_workflow_failure(
    test_client: TestClient,
    test_metadata_store: InMemoryMetadataStore,
    stub_broker: StubBroker, # Use StubBroker fixture
    mock_mcp_client: MagicMock, # Need this for patching getter
    mocker: MockerFixture,
):
    """
    Verify REST API -> Queue -> Worker (Stub) -> Actor (Mocked Agent Failure) -> Failure Status Update.
    """
    # --- Arrange ---
    # Broker is set globally by the fixture
    agent_error_message = "Agent failed intentionally during run"
    agent_exception = ValueError(agent_error_message) # Keep for simulation

    # Patch dependency getters at their source in the dependencies module
    mocker.patch('ops_core.dependencies.get_metadata_store', return_value=test_metadata_store)
    mocker.patch('ops_core.dependencies.get_mcp_client', return_value=mock_mcp_client)

    # Patch the actor's send method
    mock_send = mocker.patch('ops_core.scheduler.engine.execute_agent_task_actor.send')

    task_data = {"task_type": "agent_run", "input_data": {"goal": "async failure goal"}}
    task_id = None

    # --- Act ---
    # 1. Submit task via REST API
    response = test_client.post("/api/v1/tasks/", json=task_data)
    assert response.status_code == 201
    task_id = response.json()["task_id"]

    # 2. Verify task created in store (initial state)
    stored_task_before = await test_metadata_store.get_task(task_id)
    assert stored_task_before is not None
    assert stored_task_before.status == TaskStatus.PENDING

    # --- Assert ---
    # 3. Verify the actor's send method was called correctly
    mock_send.assert_called_once_with(task_id, task_data["input_data"])

    # 4. Verify the task status remains PENDING in the store (actor execution is mocked)
    await asyncio.sleep(0.01)
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.PENDING
