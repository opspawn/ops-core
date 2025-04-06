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

# Import the servicer and generated types from the renamed directory
from ops_core.grpc_internal.task_servicer import TaskServicer
from ops_core.grpc_internal import tasks_pb2, tasks_pb2_grpc # Corrected typo: grpcc -> grpc

# Import core components and models for mocking
from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.models import Task as CoreTask, TaskStatus as CoreTaskStatus

# --- Fixtures ---

@pytest.fixture
def mock_metadata_store() -> AsyncMock:
    """Provides a mock InMemoryMetadataStore."""
    return AsyncMock(spec=InMemoryMetadataStore)

@pytest.fixture
def mock_scheduler(mock_metadata_store: AsyncMock) -> AsyncMock:
    """Provides a mock InMemoryScheduler with a mocked _metadata_store."""
    scheduler = AsyncMock(spec=InMemoryScheduler)
    # Configure the mock to have the private attribute the servicer expects
    scheduler._metadata_store = mock_metadata_store
    return scheduler

@pytest.fixture
def task_servicer(mock_scheduler: AsyncMock) -> TaskServicer:
    """Provides an instance of TaskServicer with mocked dependencies."""
    return TaskServicer(scheduler=mock_scheduler)

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
async def test_get_task_success(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test successful task retrieval via gRPC GetTask.
    """
    # Arrange
    task_id = "grpc_task_2"
    request = tasks_pb2.GetTaskRequest(task_id=task_id)
    mock_core_task = CoreTask(
        task_id=task_id,
        task_type="data_fetch",
        status=CoreTaskStatus.RUNNING,
        input_data={"url": "http://example.com"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    # Access the mocked store via the private attribute set in the fixture
    mock_scheduler._metadata_store.get_task.return_value = mock_core_task

    # Act
    response = await task_servicer.GetTask(request, mock_grpc_context)

    # Assert
    # Verify the call on the mocked store directly
    mock_scheduler._metadata_store.get_task.assert_awaited_once_with(task_id)
    assert isinstance(response, tasks_pb2.GetTaskResponse)
    assert response.task.task_id == task_id
    assert response.task.task_type == mock_core_task.task_type
    assert response.task.status == tasks_pb2.RUNNING
    assert response.task.started_at is not None
    mock_grpc_context.abort.assert_not_called()

@pytest.mark.asyncio
async def test_get_task_not_found(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test task retrieval failure when task is not found.
    """
    # Arrange
    task_id = "not_found_task"
    request = tasks_pb2.GetTaskRequest(task_id=task_id)
    # Access the mocked store via the private attribute set in the fixture
    mock_scheduler._metadata_store.get_task.return_value = None

    # Act
    await task_servicer.GetTask(request, mock_grpc_context)

    # Assert
    # Verify the call on the mocked store directly
    mock_scheduler._metadata_store.get_task.assert_awaited_once_with(task_id)
    # Use imported StatusCode
    mock_grpc_context.abort.assert_awaited_once_with(
        StatusCode.NOT_FOUND, f"Task with ID '{task_id}' not found."
    )

@pytest.mark.asyncio
async def test_list_tasks_success(task_servicer: TaskServicer, mock_scheduler: AsyncMock, mock_grpc_context: AsyncMock):
    """
    Test successful task listing via gRPC ListTasks.
    """
    # Arrange
    request = tasks_pb2.ListTasksRequest()
    now = datetime.now(timezone.utc)
    mock_core_tasks = [
        CoreTask(task_id="task_a", task_type="type1", status=CoreTaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now),
        CoreTask(task_id="task_b", task_type="type2", status=CoreTaskStatus.PENDING, input_data={}, created_at=now, updated_at=now),
    ]
    # Access the mocked store via the private attribute set in the fixture
    mock_scheduler._metadata_store.list_tasks.return_value = mock_core_tasks

    # Act
    response = await task_servicer.ListTasks(request, mock_grpc_context)

    # Assert
    # Verify the call on the mocked store directly
    mock_scheduler._metadata_store.list_tasks.assert_awaited_once()
    assert isinstance(response, tasks_pb2.ListTasksResponse)
    assert len(response.tasks) == 2
    assert response.total == 2
    assert response.tasks[0].task_id == "task_a"
    assert response.tasks[1].task_id == "task_b"
    assert response.tasks[0].status == tasks_pb2.COMPLETED
    assert response.tasks[1].status == tasks_pb2.PENDING
    mock_grpc_context.abort.assert_not_called()
