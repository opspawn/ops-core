"""
Unit tests for the Tasks API endpoints using real dependencies and per-test mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Import the FastAPI app instance
from ops_core.main import app
# Import the dependency functions we need to override/patch
from ops_core.dependencies import get_scheduler # Only need get_scheduler for patching
# Import necessary models and schemas
from ops_core.models.tasks import Task, TaskStatus
from ops_core.metadata.sql_store import SqlMetadataStore # Import real store
from ops_core.api.v1.schemas.tasks import TaskResponse, TaskListResponse


# --- Mocks ---
# Keep scheduler mock instance for use in patches
mock_scheduler = AsyncMock()


# --- Test Client ---
# Use the app instance directly. Dependencies are handled by the app itself now.
client = TestClient(app)


# --- Test Cases ---

# Note: Tests interacting with DB need the db_session fixture for setup/cleanup.
# Scheduler mocking is now done per-test using patch.
@patch("ops_core.api.v1.endpoints.tasks.get_scheduler", return_value=mock_scheduler)
def test_create_task_success(mock_get_scheduler): # No db_session needed
    """
    Test successful task creation via POST /tasks/.
    Scheduler is mocked via patch.
    """
    # Arrange
    # Reset the mock scheduler before this test
    mock_scheduler.reset_mock()
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    expected_task_id = "new_task_123"
    # Configure mock scheduler return value
    mock_scheduler.submit_task.return_value = Task(
        task_id=expected_task_id,
        task_type=task_data["task_type"],
        status=TaskStatus.PENDING,
        input_data=task_data["input_data"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Act
    response = client.post("/api/v1/tasks/", json=task_data)

    # Assert
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["task_id"] == expected_task_id
    assert response_data["task_type"] == task_data["task_type"]
    assert response_data["input_data"] == task_data["input_data"]
    assert response_data["status"] == TaskStatus.PENDING.value
    # Check that the scheduler was called correctly
    mock_scheduler.submit_task.assert_awaited_once_with(
        name=f"API Task - {task_data['task_type']}",
        task_type=task_data["task_type"],
        input_data=task_data["input_data"]
    )


@patch("ops_core.api.v1.endpoints.tasks.get_scheduler", return_value=mock_scheduler)
def test_create_task_scheduler_error(mock_get_scheduler): # No db_session needed
    """
    Test task creation failure when scheduler raises an exception.
    """
    # Arrange
    # Reset the mock scheduler before this test
    mock_scheduler.reset_mock()
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    mock_scheduler.submit_task.side_effect = Exception("Scheduler boom!")

    # Act
    response = client.post("/api/v1/tasks/", json=task_data)

    # Assert
    assert response.status_code == 500
    assert "Failed to submit task: Scheduler boom!" in response.json()["detail"]
    mock_scheduler.submit_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_task_success(db_session: AsyncSession): # No override fixture needed
    """
    Test successful retrieval of a task via GET /tasks/{task_id} using real DB.
    """
    # Arrange: Create a task directly in the DB
    task_id = "task_get_db_abc_789"
    db_task = Task(
        task_id=task_id,
        name="DB Get Task",
        task_type="data_processing",
        status=TaskStatus.RUNNING,
        input_data={"file": "input.csv"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(db_task)
    await db_session.commit() # Commit before making the API call
    await db_session.close() # Close session before API call

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["task_id"] == task_id
    assert response_data["task_type"] == db_task.task_type
    assert response_data["status"] == TaskStatus.RUNNING.value
    assert response_data["input_data"] == db_task.input_data
    assert response_data["started_at"] is not None


@pytest.mark.asyncio # Mark as async
async def test_get_task_not_found(db_session: AsyncSession): # No override fixture needed, needs async
    """
    Test retrieval of a non-existent task via GET /tasks/{task_id} using real DB.
    """
    # Arrange
    task_id = "non_existent_task_db"
    # Ensure task does not exist (db_session fixture handles cleanup)
    await db_session.close() # Close session before API call

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == f"Task with ID '{task_id}' not found."


@pytest.mark.asyncio
async def test_get_task_metadata_store_error(db_session: AsyncSession, mocker): # No override fixture needed
    """
    Test retrieval failure when metadata store raises an exception (simulated DB error).
    """
    # Arrange
    task_id = "error_task_id_db"
    error_message = "Simulated database connection failed"

    # Create a task in DB so the endpoint tries to fetch it
    db_task = Task(task_id=task_id, name="Error Task", task_type="error_test", status=TaskStatus.PENDING)
    db_session.add(db_task)
    await db_session.commit() # Commit before making the API call

    # Patch the SqlMetadataStore's get_task method directly
    # We need to patch the method within the module where it's used by the dependency injector
    mocker.patch("ops_core.dependencies.SqlMetadataStore.get_task", side_effect=Exception(error_message))

    await db_session.close() # Close session before API call

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}")

    # Assert
    assert response.status_code == 500
    assert "Failed to retrieve task" in response.json()["detail"]


@pytest.mark.asyncio # Mark as async
async def test_list_tasks_success_empty(db_session: AsyncSession): # No override fixture needed, needs async
    """
    Test successful listing of tasks when none exist via GET /tasks/ using real DB.
    """
    # Arrange (Ensure DB is empty - handled by fixture)
    await db_session.close() # Close session before API call

    # Act
    response = client.get("/api/v1/tasks/")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["tasks"] == []
    assert response_data["total"] == 0


@pytest.mark.asyncio
async def test_list_tasks_success_with_data(db_session: AsyncSession): # No override fixture needed
    """
    Test successful listing of tasks when some exist via GET /tasks/ using real DB.
    """
    # Arrange: Create tasks directly in the DB
    now = datetime.now(timezone.utc)
    task1 = Task(task_id="db_task1", name="DB Task 1", task_type="typeA", status=TaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now)
    task2 = Task(task_id="db_task2", name="DB Task 2", task_type="typeB", status=TaskStatus.PENDING, input_data={}, created_at=now, updated_at=now)
    db_session.add_all([task1, task2])
    await db_session.commit() # Commit before making the API call
    await db_session.close() # Close session before API call

    # Act
    response = client.get("/api/v1/tasks/")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["tasks"]) == 2
    assert response_data["total"] == 2
    # Check presence and basic details (order might not be guaranteed)
    task_ids_in_response = {t["task_id"] for t in response_data["tasks"]}
    assert "db_task1" in task_ids_in_response
    assert "db_task2" in task_ids_in_response
    # Find task1 data to check status
    task1_data = next((t for t in response_data["tasks"] if t["task_id"] == "db_task1"), None)
    assert task1_data is not None
    assert task1_data["status"] == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_list_tasks_metadata_store_error(db_session: AsyncSession, mocker): # No override fixture needed
    """
    Test listing failure when metadata store raises an exception (simulated DB error).
    """
    # Arrange
    error_message = "Simulated failed to query tasks"
    # Patch the SqlMetadataStore's list_tasks method directly
    mocker.patch("ops_core.dependencies.SqlMetadataStore.list_tasks", side_effect=Exception(error_message))
    await db_session.close() # Close session before API call

    # Act
    response = client.get("/api/v1/tasks/")

    # Assert
    assert response.status_code == 500
    assert f"Failed to list tasks" in response.json()["detail"]


# --- Input Validation Tests ---

# These tests don't interact with the store/scheduler, so they don't need db_session or overrides
def test_create_task_missing_task_type():
    """
    Test task creation with missing 'task_type' field.
    """
    # Arrange
    invalid_task_data = {"input_data": {"prompt": "hello"}} # Missing task_type

    # Act
    response = client.post("/api/v1/tasks/", json=invalid_task_data)

    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    assert any(err["msg"] == "Field required" and "task_type" in err["loc"] for err in response_data["detail"])


def test_create_task_invalid_input_data_type():
    """
    Test task creation with invalid type for 'input_data' (should be dict).
    """
    # Arrange
    invalid_task_data = {"task_type": "agent_run", "input_data": "not_a_dictionary"}

    # Act
    response = client.post("/api/v1/tasks/", json=invalid_task_data)

    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    # Pydantic v2 message for wrong type
    assert any("Input should be a valid dictionary" in err["msg"] and "input_data" in err["loc"] for err in response_data["detail"])


# TODO: Add more specific input validation tests if TaskCreateRequest schema becomes stricter
# TODO: Add tests for pagination if implemented in list_tasks
