"""
Integration tests for the full asynchronous task workflow:
API -> Metadata Store -> Message Queue -> Worker (Simulated) -> Actor -> Metadata Store Update
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
from ops_core.main import app as fastapi_app
from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.models.tasks import Task, TaskStatus
from ops_core.api.v1.endpoints import tasks as tasks_api
import dramatiq # Import the main dramatiq library
from dramatiq.brokers.stub import StubBroker # Import StubBroker directly

# Import dependencies container
from ops_core.dependencies import deps

from ops_core.grpc_internal.task_servicer import TaskServicer
from ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc
from ops_core.scheduler.engine import execute_agent_task_actor # Import the actor

# --- Test Configuration ---

# Configure Dramatiq for testing:
# - Use StubBroker to check if messages are enqueued.
stub_broker = StubBroker() # Instantiate directly
stub_broker.emit_after("process_boot") # Important for StubBroker
# Declare the queue used by the actor on the stub broker
stub_broker.declare_queue(execute_agent_task_actor.queue_name)
dramatiq.set_broker(stub_broker) # Override the global broker


# --- Fixtures ---

@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_broker_and_deps():
    """Clears messages and resets deps before/after each test."""
    stub_broker.flush_all()
    # Reset dependencies container
    original_store = deps.metadata_store
    original_client = deps.mcp_client
    deps.metadata_store = None
    deps.mcp_client = None
    yield
    # Clear after test
    stub_broker.flush_all()
    # Restore original deps if they existed
    deps.metadata_store = original_store
    deps.mcp_client = original_client


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
        mcp_client=mock_mcp_client
    )
    return scheduler

@pytest.fixture
def test_client(
    test_scheduler: InMemoryScheduler,
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock
) -> TestClient:
    """Provides a FastAPI TestClient with overridden dependencies."""
    from ops_core.dependencies import get_metadata_store as api_get_store
    from ops_core.dependencies import get_mcp_client as api_get_client

    # Ensure deps are set for the API context
    deps.metadata_store = test_metadata_store
    deps.mcp_client = mock_mcp_client

    fastapi_app.dependency_overrides[api_get_store] = lambda: test_metadata_store
    fastapi_app.dependency_overrides[api_get_client] = lambda: mock_mcp_client
    fastapi_app.dependency_overrides[tasks_api.get_scheduler] = lambda: test_scheduler

    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides = {}


@pytest_asyncio.fixture(scope="function")
async def grpc_server(test_scheduler: InMemoryScheduler):
    """Starts an in-process gRPC server for testing."""
    server = grpc_aio.server()
    deps.metadata_store = test_scheduler._metadata_store
    deps.mcp_client = test_scheduler._mcp_client
    tasks_pb2_grpc.add_TaskServiceServicer_to_server(
        TaskServicer(scheduler=test_scheduler), server
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

# --- Mocks for Actor ---

@pytest_asyncio.fixture
def mock_agent_run():
    """Provides a mock for the Agent.run method."""
    async def _run(*args, **kwargs):
        # Simulate agent result structure based on actor code
        return {"result": "agent finished successfully"}
    mock = AsyncMock(side_effect=_run)
    mock._mock_name = "mock_agent_run"
    return mock

@pytest_asyncio.fixture
def mock_agent_cls(mock_agent_run):
    """Provides a mock Agent class."""
    mock_agent_instance = MagicMock()
    # Assume actor calls agent.run(goal=...)
    mock_agent_instance.run = mock_agent_run
    # Mock memory if actor accesses it
    mock_agent_instance.memory = MagicMock()
    mock_agent_instance.memory.get_history = MagicMock(return_value=["history item"])
    mock_agent_cls = MagicMock(return_value=mock_agent_instance)
    mock_agent_cls._mock_name = "mock_agent_cls"
    return mock_agent_cls


# --- Test Cases ---

@pytest.mark.asyncio
async def test_rest_api_async_agent_workflow_success(
    test_client: TestClient,
    test_scheduler: InMemoryScheduler, # Scheduler fixture sets deps
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock,
    mock_agent_cls: MagicMock,
    mock_agent_run: AsyncMock,
):
    """
    Verify REST API -> Queue -> Worker (Simulated) -> Actor -> Success Status Update.
    """
    task_data = {"task_type": "agent_run", "input_data": {"goal": "async rest goal"}}
    task_id = None

    # 1. Submit task via REST API
    response = test_client.post("/api/v1/tasks/", json=task_data)

    assert response.status_code == 201
    response_json = response.json()
    task_id = response_json["task_id"]
    assert response_json["status"] == TaskStatus.PENDING.value

    # 2. Verify task created in store
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING

    # 3. Verify message was enqueued
    queue = stub_broker.queues.get(execute_agent_task_actor.queue_name)
    assert queue is not None
    assert len(queue) == 1
    message = queue.get() # Consume the message for verification
    assert message.actor_name == execute_agent_task_actor.actor_name
    assert message.args == (task_id, task_data["input_data"])

    # 4. Simulate worker processing by calling the actor function directly
    #    Patch Agent where it's imported in the engine module
    with patch('ops_core.scheduler.engine.Agent', new=mock_agent_cls):
        await execute_agent_task_actor.fn(
            task_id,
            task_data["input_data"],
            _test_metadata_store=test_metadata_store, # Inject test store
            _test_mcp_client=mock_mcp_client # Inject test client
        )

    # 5. Verify Agent was instantiated and run
    mock_agent_cls.assert_called_once()
    # Check the call to the 'run' method (adjust based on actual agent method called)
    mock_agent_run.assert_awaited_once_with(goal=task_data["input_data"]["goal"])

    # 6. Verify task status updated in store
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
    # Check the result structure based on actor logic and mock_agent_run
    assert final_task.result == {
        "memory_history": ["history item"],
        "final_output": {"result": "agent finished successfully"}
    }
    assert final_task.error is None


@pytest.mark.asyncio
async def test_grpc_api_async_agent_workflow_success(
    grpc_client: tasks_pb2_grpc.TaskServiceStub,
    test_scheduler: InMemoryScheduler, # Scheduler fixture sets deps
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock,
    mock_agent_cls: MagicMock,
    mock_agent_run: AsyncMock,
):
    """
    Verify gRPC API -> Queue -> Worker (Simulated) -> Actor -> Success Status Update.
    """
    input_dict = {"goal": "async grpc goal"}
    input_struct = tasks_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    input_struct.update(input_dict)
    request = tasks_pb2.CreateTaskRequest(
        task_type="agent_run", input_data=input_struct
    )
    task_id = None

    # 1. Submit task via gRPC API
    response = await grpc_client.CreateTask(request)

    assert response.task.task_type == "agent_run"
    assert response.task.status == tasks_pb2.PENDING
    task_id = response.task.task_id

    # 2. Verify task created in store
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING

    # 3. Verify message was enqueued
    queue = stub_broker.queues.get(execute_agent_task_actor.queue_name)
    assert queue is not None
    assert len(queue) == 1
    message = queue.get()
    assert message.actor_name == execute_agent_task_actor.actor_name
    assert message.args == (task_id, input_dict)

    # 4. Simulate worker processing
    with patch('ops_core.scheduler.engine.Agent', new=mock_agent_cls):
        await execute_agent_task_actor.fn(
            task_id,
            input_dict, # Pass the dict extracted from proto
            _test_metadata_store=test_metadata_store,
            _test_mcp_client=mock_mcp_client
        )

    # 5. Verify Agent was instantiated and run
    mock_agent_cls.assert_called_once()
    mock_agent_run.assert_awaited_once_with(goal=input_dict["goal"])

    # 6. Verify task status updated in store
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.result == {
        "memory_history": ["history item"],
        "final_output": {"result": "agent finished successfully"}
    }
    assert final_task.error is None


@pytest.mark.asyncio
async def test_rest_api_async_agent_workflow_failure(
    test_client: TestClient,
    test_scheduler: InMemoryScheduler, # Scheduler fixture sets deps
    test_metadata_store: InMemoryMetadataStore,
    mock_mcp_client: MagicMock,
    mock_agent_cls: MagicMock,
    mock_agent_run: AsyncMock,
):
    """
    Verify REST API -> Queue -> Worker (Simulated) -> Actor (Failure) -> Failure Status Update.
    """
    task_data = {"task_type": "agent_run", "input_data": {"goal": "async failure goal"}}
    task_id = None
    agent_error_message = "Agent failed intentionally"
    # Make the mock run method raise an exception
    mock_agent_run.side_effect = Exception(agent_error_message)

    # 1. Submit task via REST API
    response = test_client.post("/api/v1/tasks/", json=task_data)
    assert response.status_code == 201
    task_id = response.json()["task_id"]

    # 2. Verify task created
    stored_task = await test_metadata_store.get_task(task_id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.PENDING

    # 3. Verify message was enqueued
    queue = stub_broker.queues.get(execute_agent_task_actor.queue_name)
    assert queue is not None
    assert len(queue) == 1
    message = queue.get()
    assert message.actor_name == execute_agent_task_actor.actor_name
    assert message.args == (task_id, task_data["input_data"])

    # 4. Simulate worker processing
    with patch('ops_core.scheduler.engine.Agent', new=mock_agent_cls):
        await execute_agent_task_actor.fn(
            task_id,
            task_data["input_data"],
            _test_metadata_store=test_metadata_store,
            _test_mcp_client=mock_mcp_client
        )

    # 5. Verify Agent was instantiated and run (and failed)
    mock_agent_cls.assert_called_once()
    mock_agent_run.assert_awaited_once_with(goal=task_data["input_data"]["goal"])

    # 6. Verify task status updated to FAILED in store
    final_task = await test_metadata_store.get_task(task_id)
    assert final_task is not None
    assert final_task.status == TaskStatus.FAILED
    assert final_task.result is None
    # Check that the error message includes the original exception details
    assert agent_error_message in final_task.error
    assert "Exception" in final_task.error # Check type name is included
    assert "Traceback" in final_task.error # Check traceback is included
