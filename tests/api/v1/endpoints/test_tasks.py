"""
Unit tests for the Tasks API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Import the FastAPI app instance
from src.ops_core.main import app
# Import the dependency functions we need to override
from src.ops_core.dependencies import get_scheduler, get_metadata_store, get_db_session
# Import necessary models and schemas
from src.ops_core.models.tasks import Task, TaskStatus
from src.ops_core.metadata.sql_store import SqlMetadataStore # Import real store
from src.ops_core.api.v1.schemas.tasks import TaskResponse, TaskListResponse


# --- Mocks ---
# Keep scheduler mock for now as create_task depends on it
mock_scheduler = AsyncMock()
# Remove metadata store mock
# mock_metadata_store = AsyncMock()


# --- Fixtures ---
@pytest.fixture(scope="function")
def override_dependencies_in_app(db_session: AsyncSession):
    """
    Fixture to override dependencies for each test function.
    Provides a real SqlMetadataStore using the test db_session.
    Keeps the scheduler mocked.
    """
    # Override get_db_session to return the test session
    app.dependency_overrides[get_db_session] = lambda: db_session

    # Override get_metadata_store to use the overridden get_db_session
    # Note: FastAPI handles resolving the Depends(get_db_session) within get_metadata_store
    # So we just need to override get_db_session itself.
    # We don't need to explicitly override get_metadata_store unless we want to mock it.

    # Override scheduler
    app.dependency_overrides[get_scheduler] = lambda: mock_scheduler

    yield  # Run the test

    # Clean up overrides after test function finishes
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset scheduler mock before each test."""
    mock_scheduler.reset_mock()
    # Set default return values for mocked methods
    mock_scheduler.submit_task.return_value = Task(
        task_id="new_task_123",
        task_type="test_task",
        status=TaskStatus.PENDING,
        input_data={"key": "value"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Remove store mock resets
    # mock_metadata_store.reset_mock()
    # mock_metadata_store.get_task.return_value = None
    # mock_metadata_store.list_tasks.return_value = []


# --- Test Client ---
# Use the app instance directly, overrides are handled by the fixture
client = TestClient(app)


# --- Test Cases ---

# Use the override fixture implicitly via autouse=True
def test_create_task_success(override_dependencies_in_app):
    """
    Test successful task creation via POST /tasks/.
    Scheduler is mocked, store interaction happens within scheduler.
    """
    # Arrange
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
    # Note: We don't verify DB state here as the scheduler (which writes to DB) is mocked.


# Use the override fixture implicitly via autouse=True
def test_create_task_scheduler_error(override_dependencies_in_app):
    """
    Test task creation failure when scheduler raises an exception.
    """
    # Arrange
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    mock_scheduler.submit_task.side_effect = Exception("Scheduler boom!")

    # Act
    response = client.post("/api/v1/tasks/", json=task_data)

    # Assert
    assert response.status_code == 500
    assert "Failed to submit task: Scheduler boom!" in response.json()["detail"]
    mock_scheduler.submit_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_task_success(override_dependencies_in_app, db_session: AsyncSession):
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
    await db_session.commit()
    await db_session.refresh(db_task) # Ensure all fields are loaded

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
    # No mock store to assert calls against


def test_get_task_not_found(override_dependencies_in_app, db_session: AsyncSession):
    """
    Test retrieval of a non-existent task via GET /tasks/{task_id} using real DB.
    """
    # Arrange
    task_id = "non_existent_task_db"
    # Ensure task does not exist (db_session fixture handles cleanup)

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == f"Task with ID '{task_id}' not found."
    # No mock store to assert calls against


@pytest.mark.asyncio
async def test_get_task_metadata_store_error(override_dependencies_in_app, db_session: AsyncSession, mocker):
    """
    Test retrieval failure when metadata store raises an exception (simulated DB error).
    """
    # Arrange
    task_id = "error_task_id_db"
    error_message = "Simulated database connection failed"

    # Create a task in DB so the endpoint tries to fetch it
    db_task = Task(task_id=task_id, name="Error Task", task_type="error_test", status=TaskStatus.PENDING)
    db_session.add(db_task)
    await db_session.commit()

    # Patch the session's execute method to raise an error when called by get_task
    mocker.patch.object(db_session, "execute", side_effect=Exception(error_message))

    # Act
    response = client.get(f"/api/v1/tasks/{task_id}")

    # Assert
    assert response.status_code == 500
    # The exact detail might vary depending on how the exception propagates
    assert "Failed to retrieve task" in response.json()["detail"]
    # Check if the detail includes the simulated error message (optional, might be too specific)
    # assert error_message in response.json()["detail"]


def test_list_tasks_success_empty(override_dependencies_in_app, db_session: AsyncSession):
    """
    Test successful listing of tasks when none exist via GET /tasks/ using real DB.
    """
    # Arrange (Ensure DB is empty - handled by fixture)

    # Act
    response = client.get("/api/v1/tasks/")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["tasks"] == []
    assert response_data["total"] == 0
    # No mock store to assert calls against


@pytest.mark.asyncio
async def test_list_tasks_success_with_data(override_dependencies_in_app, db_session: AsyncSession):
    """
    Test successful listing of tasks when some exist via GET /tasks/ using real DB.
    """
    # Arrange: Create tasks directly in the DB
    now = datetime.now(timezone.utc)
    task1 = Task(task_id="db_task1", name="DB Task 1", task_type="typeA", status=TaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now)
    task2 = Task(task_id="db_task2", name="DB Task 2", task_type="typeB", status=TaskStatus.PENDING, input_data={}, created_at=now, updated_at=now)
    db_session.add_all([task1, task2])
    await db_session.commit()

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
    # No mock store to assert calls against


@pytest.mark.asyncio
async def test_list_tasks_metadata_store_error(override_dependencies_in_app, db_session: AsyncSession, mocker):
    """
    Test listing failure when metadata store raises an exception (simulated DB error).
    """
    # Arrange
    error_message = "Simulated failed to query tasks"
    # Patch the session's execute method to raise an error when called by list_tasks
    mocker.patch.object(db_session, "execute", side_effect=Exception(error_message))

    # Act
    response = client.get("/api/v1/tasks/")

    # Assert
    assert response.status_code == 500
    assert f"Failed to list tasks" in response.json()["detail"]
    # assert error_message in response.json()["detail"] # Optional check


# --- Input Validation Tests ---

# These tests don't interact with the store/scheduler, so they don't need db_session
def test_create_task_missing_task_type(override_dependencies_in_app):
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
