"""
Unit tests for the Tasks API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

# Import the FastAPI app instance
# Need to ensure dependencies are mocked *before* the app is imported
# if dependencies are created at module level in endpoints/tasks.py
# Patching the singleton instances directly for now.

# Mock the singleton instances BEFORE importing the app or router
# Import the app first
from ops_core.main import app
# Import the dependency functions we need to override
from ops_core.api.v1.endpoints.tasks import get_scheduler, get_metadata_store
# Import necessary models and schemas
from ops_core.models.tasks import Task, TaskStatus
from ops_core.api.v1.schemas.tasks import TaskResponse, TaskListResponse


# --- Mocks ---
mock_scheduler = AsyncMock()
mock_metadata_store = AsyncMock()


# --- Fixtures ---
@pytest.fixture(scope="function", autouse=True)
def override_dependencies_in_app():
    """Fixture to override dependencies for each test function."""
    app.dependency_overrides[get_scheduler] = lambda: mock_scheduler
    app.dependency_overrides[get_metadata_store] = lambda: mock_metadata_store
    yield  # Run the test
    # Clean up overrides after test function finishes
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    mock_scheduler.reset_mock()
    mock_metadata_store.reset_mock()
    # Set default return values for mocked methods
    mock_scheduler.submit_task.return_value = Task(
        task_id="new_task_123",
        task_type="test_task",
        status=TaskStatus.PENDING,
        input_data={"key": "value"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_metadata_store.get_task.return_value = None  # Default to not found
    mock_metadata_store.list_tasks.return_value = []  # Default to empty list


# --- Test Client ---
# Create the TestClient using the app with potentially overridden dependencies
client = TestClient(app)


# --- Test Cases ---

def test_create_task_success():
    """
    Test successful task creation via POST /tasks/.
    """
    # Arrange
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    expected_task_id = "new_task_123"
    mock_scheduler.submit_task.return_value = Task(
        task_id=expected_task_id,
        task_type=task_data["task_type"],
        status=TaskStatus.PENDING,
        input_data=task_data["input_data"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Act
    response = client.post("/api/v1/tasks/", json=task_data) # Added prefix

    # Assert
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["task_id"] == expected_task_id
    assert response_data["task_type"] == task_data["task_type"]
    assert response_data["input_data"] == task_data["input_data"]
    assert response_data["status"] == TaskStatus.PENDING.value
    # Check that the name argument was included in the call
    mock_scheduler.submit_task.assert_awaited_once_with(
        name=f"API Task - {task_data['task_type']}", # Add name check
        task_type=task_data["task_type"],
        input_data=task_data["input_data"]
    )


def test_create_task_scheduler_error():
    """
    Test task creation failure when scheduler raises an exception.
    """
    # Arrange
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    mock_scheduler.submit_task.side_effect = Exception("Scheduler boom!")

    # Act
    response = client.post("/api/v1/tasks/", json=task_data) # Added prefix

    # Assert
    assert response.status_code == 500
    assert "Failed to submit task: Scheduler boom!" in response.json()["detail"]
    mock_scheduler.submit_task.assert_awaited_once()


def test_get_task_success():
    """
    Test successful retrieval of a task via GET /tasks/{task_id}.
    """
    # Arrange
    task_id = "task_abc_789"
    mock_task = Task(
        task_id=task_id,
        task_type="data_processing",
        status=TaskStatus.RUNNING,
        input_data={"file": "input.csv"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    mock_metadata_store.get_task.return_value = mock_task

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}") # Added prefix

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["task_id"] == task_id
    assert response_data["task_type"] == mock_task.task_type
    assert response_data["status"] == TaskStatus.RUNNING.value
    assert response_data["input_data"] == mock_task.input_data
    assert response_data["started_at"] is not None
    mock_metadata_store.get_task.assert_awaited_once_with(task_id)


def test_get_task_not_found():
    """
    Test retrieval of a non-existent task via GET /tasks/{task_id}.
    """
    # Arrange
    task_id = "non_existent_task"
    mock_metadata_store.get_task.return_value = None # Explicitly set for clarity

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}") # Added prefix

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == f"Task with ID '{task_id}' not found."
    mock_metadata_store.get_task.assert_awaited_once_with(task_id)


def test_list_tasks_success_empty():
    """
    Test successful listing of tasks when none exist via GET /tasks/.
    """
    # Arrange
    mock_metadata_store.list_tasks.return_value = []

    # Act
    response = client.get("/api/v1/tasks/") # Added prefix

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["tasks"] == []
    assert response_data["total"] == 0
    mock_metadata_store.list_tasks.assert_awaited_once()


def test_list_tasks_success_with_data():
    """
    Test successful listing of tasks when some exist via GET /tasks/.
    """
    # Arrange
    now = datetime.now(timezone.utc)
    mock_tasks = [
        Task(task_id="task1", task_type="typeA", status=TaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now), # Added input_data
        Task(task_id="task2", task_type="typeB", status=TaskStatus.PENDING, input_data={}, created_at=now, updated_at=now), # Added input_data
    ]
    mock_metadata_store.list_tasks.return_value = mock_tasks

    # Act
    response = client.get("/api/v1/tasks/") # Added prefix

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["tasks"]) == 2
    assert response_data["total"] == 2
    assert response_data["tasks"][0]["task_id"] == "task1"
    assert response_data["tasks"][1]["task_id"] == "task2"
    assert response_data["tasks"][0]["status"] == TaskStatus.COMPLETED.value
    mock_metadata_store.list_tasks.assert_awaited_once()

# TODO: Add tests for invalid input data on POST /tasks/ if validation is added
# TODO: Add tests for pagination if implemented in list_tasks
