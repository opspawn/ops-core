"""
Unit tests for the TaskServicer gRPC implementation.
"""

import pytest
# Explicitly import required submodules instead of top-level grpc
from grpc import aio as grpc_aio
from grpc import StatusCode
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from google.protobuf import struct_pb2
from sqlalchemy.ext.asyncio import AsyncSession

# Import the servicer and generated types from the renamed directory
from ops_core.grpc_internal.task_servicer import TaskServicer
from ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc

# Import core components and models
from ops_core.scheduler.engine import InMemoryScheduler # Keep for mocking
from ops_core.metadata.sql_store import SqlMetadataStore # Import real store
from ops_core.models import Task as CoreTask, TaskStatus as CoreTaskStatus

# --- Fixtures ---

# Remove mock_metadata_store fixture
# @pytest.fixture
# def mock_metadata_store() -> AsyncMock:
#     """Provides a mock InMemoryMetadataStore."""
#     return AsyncMock(spec=InMemoryMetadataStore)

@pytest.fixture
def mock_scheduler() -> AsyncMock:
    """Provides a mock InMemoryScheduler."""
    # No longer needs to hold a mock store
    scheduler = AsyncMock(spec=InMemoryScheduler)
    return scheduler

@pytest.fixture
def task_servicer(
    mock_scheduler: AsyncMock,
    db_session: AsyncSession # Inject db session
) -> TaskServicer:
    """Provides an instance of TaskServicer with a mocked scheduler and real SqlMetadataStore."""
    # Create real store instance, passing the test session
    sql_store = SqlMetadataStore(session=db_session) # Pass the session
    # Inject mock scheduler and real store
    return TaskServicer(scheduler=mock_scheduler, metadata_store=sql_store)

@pytest.fixture
def mock_grpc_context() -> AsyncMock:
    """Provides a mock gRPC ServicerContext."""
    # Use imported aio for spec
    return AsyncMock(spec=grpc_aio.ServicerContext)

# --- Helper ---
def _dict_to_struct(data: dict) -> struct_pb2.Struct:
    s = struct_pb2.Struct()
    s.update(data)
    return s

# --- Test Cases ---

@pytest.mark.asyncio
async def test_create_task_success(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test successful task creation via gRPC CreateTask.
    """
    # Arrange
    input_dict = {"prompt": "generate report"}
    request = tasks_pb2.CreateTaskRequest(
        task_type="report_gen",
        input_data=_dict_to_struct(input_dict)
    )
    mock_core_task = CoreTask(
        task_id="grpc_task_1",
        task_type="report_gen",
        status=CoreTaskStatus.PENDING,
        input_data=input_dict,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_scheduler.submit_task.return_value = mock_core_task

    # Act
    response = await task_servicer.CreateTask(request, mock_grpc_context)

    # Assert
    # Check that the name argument was included in the call
    mock_scheduler.submit_task.assert_awaited_once_with(
        name=f"gRPC Task - {request.task_type}", # Add name check
        task_type=request.task_type,
        input_data=input_dict
    )
    assert isinstance(response, tasks_pb2.CreateTaskResponse)
    assert response.task.task_id == mock_core_task.task_id
    assert response.task.task_type == mock_core_task.task_type
    assert response.task.status == tasks_pb2.PENDING
    assert dict(response.task.input_data.items()) == input_dict
    mock_grpc_context.abort.assert_not_called()

@pytest.mark.asyncio
async def test_create_task_scheduler_error(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test task creation failure when the scheduler raises an error.
    """
    # Arrange
    input_dict = {"prompt": "fail me"}
    request = tasks_pb2.CreateTaskRequest(
        task_type="error_task",
        input_data=_dict_to_struct(input_dict)
    )
    error_message = "Scheduler failed!"
    mock_scheduler.submit_task.side_effect = Exception(error_message)

    # Act
    await task_servicer.CreateTask(request, mock_grpc_context)

    # Assert
    # Check that the name argument was included in the call
    mock_scheduler.submit_task.assert_awaited_once_with(
        name=f"gRPC Task - {request.task_type}", # Add name check
        task_type=request.task_type,
        input_data=input_dict
    )
    # Use imported StatusCode
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.INTERNAL, f"Failed to create task: {error_message}"
    )

@pytest.mark.asyncio
async def test_get_task_success(
    task_servicer: TaskServicer, # Uses updated fixture with real store
    mock_grpc_context: AsyncMock,
    db_session: AsyncSession # Inject session for setup
):
    """
    Test successful task retrieval via gRPC GetTask using real DB.
    """
    # Arrange: Create task in DB
    task_id = "grpc_task_db_2"
    db_task = CoreTask(
        task_id=task_id,
        name="DB Get Task gRPC",
        task_type="data_fetch",
        status=CoreTaskStatus.RUNNING,
        input_data={"url": "http://example.com"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(db_task)
    await db_session.commit()
    await db_session.refresh(db_task)

    request = tasks_pb2.GetTaskRequest(task_id=task_id)

    # Act
    response = await task_servicer.GetTask(request, mock_grpc_context)

    # Assert
    assert isinstance(response, tasks_pb2.GetTaskResponse)
    assert response.task.task_id == task_id
    assert response.task.task_type == db_task.task_type
    assert response.task.status == tasks_pb2.RUNNING
    assert response.task.started_at is not None
    mock_grpc_context.abort.assert_not_called()
    # No mock store call to verify

@pytest.mark.asyncio
async def test_get_task_not_found(
    task_servicer: TaskServicer, # Uses updated fixture
    mock_grpc_context: AsyncMock,
    db_session: AsyncSession # Inject session to ensure clean state
):
    """
    Test task retrieval failure when task is not found using real DB.
    """
    # Arrange
    task_id = "not_found_task_grpc_db"
    request = tasks_pb2.GetTaskRequest(task_id=task_id)
    # Ensure task does not exist (handled by db_session fixture)

    # Act
    await task_servicer.GetTask(request, mock_grpc_context)

    # Assert
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.NOT_FOUND, f"Task with ID '{task_id}' not found."
    )
    # No mock store call to verify

@pytest.mark.asyncio
async def test_get_task_metadata_store_error(
    task_servicer: TaskServicer, # Uses updated fixture
    mock_grpc_context: AsyncMock,
    db_session: AsyncSession, # Inject session for setup and patching
    mocker # Inject mocker for patching
):
    """
    Test task retrieval failure when the metadata store raises an error (simulated DB error).
    """
    # Arrange: Create task in DB so servicer tries to fetch it
    task_id = "error_task_grpc_db"
    db_task = CoreTask(task_id=task_id, name="Error Task gRPC", task_type="error_test", status=CoreTaskStatus.PENDING)
    db_session.add(db_task)
    await db_session.commit()

    request = tasks_pb2.GetTaskRequest(task_id=task_id)
    error_message = "Simulated DB connection lost"
    # Patch the store's get_task method directly on the servicer instance
    mocker.patch.object(task_servicer._metadata_store, "get_task", side_effect=Exception(error_message))

    # Act
    await task_servicer.GetTask(request, mock_grpc_context)

    # Assert
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.INTERNAL, f"Failed to retrieve task: {error_message}"
    )


@pytest.mark.asyncio
async def test_create_task_missing_task_type(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test task creation failure when task_type is missing.
    """
    # Arrange
    input_dict = {"prompt": "some data"}
    # Create request without setting task_type
    request = tasks_pb2.CreateTaskRequest(
        input_data=_dict_to_struct(input_dict)
    )

    # Act
    await task_servicer.CreateTask(request, mock_grpc_context)

    # Assert
    mock_scheduler.submit_task.assert_not_awaited() # Scheduler should not be called
    # Use imported StatusCode
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.INVALID_ARGUMENT, "Task type cannot be empty."
    )

@pytest.mark.asyncio
async def test_create_task_empty_task_type(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test task creation failure when task_type is an empty string.
    """
    # Arrange
    input_dict = {"prompt": "some data"}
    # Create request with empty task_type
    request = tasks_pb2.CreateTaskRequest(
        task_type="",
        input_data=_dict_to_struct(input_dict)
    )

    # Act
    await task_servicer.CreateTask(request, mock_grpc_context)

    # Assert
    mock_scheduler.submit_task.assert_not_awaited() # Scheduler should not be called
    # Use imported StatusCode
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.INVALID_ARGUMENT, "Task type cannot be empty."
    )


@pytest.mark.asyncio
async def test_list_tasks_success(
    task_servicer: TaskServicer, # Uses updated fixture
    mock_grpc_context: AsyncMock,
    db_session: AsyncSession # Inject session for setup
):
    """
    Test successful task listing via gRPC ListTasks using real DB.
    """
    # Arrange: Create tasks in DB
    request = tasks_pb2.ListTasksRequest()
    now = datetime.now(timezone.utc)
    task_a = CoreTask(task_id="task_grpc_a", name="gRPC A", task_type="type1", status=CoreTaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now)
    task_b = CoreTask(task_id="task_grpc_b", name="gRPC B", task_type="type2", status=CoreTaskStatus.PENDING, input_data={}, created_at=now, updated_at=now)
    db_session.add_all([task_a, task_b])
    await db_session.commit()

    # Act
    response = await task_servicer.ListTasks(request, mock_grpc_context)

    # Assert
    assert isinstance(response, tasks_pb2.ListTasksResponse)
    assert len(response.tasks) == 2
    assert response.total == 2
    # Check presence and basic details (order might not be guaranteed)
    task_ids_in_response = {t.task_id for t in response.tasks}
    assert "task_grpc_a" in task_ids_in_response
    assert "task_grpc_b" in task_ids_in_response
    # Find task_a data to check status
    task_a_data = next((t for t in response.tasks if t.task_id == "task_grpc_a"), None)
    assert task_a_data is not None
    assert task_a_data.status == tasks_pb2.COMPLETED
    mock_grpc_context.abort.assert_not_called()
    # No mock store call to verify


@pytest.mark.asyncio
async def test_list_tasks_metadata_store_error(
    task_servicer: TaskServicer, # Uses updated fixture
    mock_grpc_context: AsyncMock,
    db_session: AsyncSession, # Inject session for patching
    mocker # Inject mocker
):
    """
    Test task listing failure when the metadata store raises an error (simulated DB error).
    """
    # Arrange
    request = tasks_pb2.ListTasksRequest()
    error_message = "Simulated query failed"
    # Patch the store's list_tasks method directly on the servicer instance
    mocker.patch.object(task_servicer._metadata_store, "list_tasks", side_effect=Exception(error_message))

    # Act
    await task_servicer.ListTasks(request, mock_grpc_context)

    # Assert
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.INTERNAL, f"Failed to list tasks: {error_message}"
    )
