"""
Unit tests for the Tasks API endpoints using real dependencies and per-test mocking.
"""

import pytest
import pytest_asyncio # Import pytest_asyncio
import httpx # Import httpx
from unittest.mock import AsyncMock, MagicMock, patch
# Remove TestClient import
# from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Import the FastAPI app instance
from ops_core.main import app as fastapi_app # Rename for clarity
# Import the dependency functions we need to override/patch
from ops_core.dependencies import get_scheduler, get_metadata_store, get_db_session, get_mcp_client # Import all needed
from ops_core.scheduler.engine import InMemoryScheduler # Import for fixture type hint
# Import necessary models and schemas
from ops_core.models.tasks import Task, TaskStatus
from ops_core.metadata.sql_store import SqlMetadataStore # Import real store
from ops_core.api.v1.schemas.tasks import TaskResponse, TaskListResponse


# --- Fixtures ---

@pytest_asyncio.fixture
async def mock_scheduler(db_session: AsyncSession) -> InMemoryScheduler:
    """Provides a mocked InMemoryScheduler instance for dependency override."""
    # We don't need a real store here, just the mock scheduler object
    # If tests need to assert scheduler calls that interact with store,
    # they might need a more complex fixture or direct patching.
    scheduler = AsyncMock(spec=InMemoryScheduler)
    # Mock the store within the scheduler if needed for specific tests,
    # but the dependency override will handle the store for the API endpoint.
    # scheduler.metadata_store = AsyncMock(spec=SqlMetadataStore)
    return scheduler

@pytest_asyncio.fixture
async def async_test_client(
    db_session: AsyncSession,
    mock_scheduler: AsyncMock # Use the simpler mock scheduler fixture
) -> httpx.AsyncClient:
    """Provides an httpx.AsyncClient with overridden dependencies."""
    # Import original dependencies
    from ops_core.dependencies import get_db_session as original_get_db_session
    from ops_core.dependencies import get_scheduler as original_get_scheduler
    from ops_core.dependencies import get_metadata_store as original_get_metadata_store

    # Override get_db_session
    fastapi_app.dependency_overrides[original_get_db_session] = lambda: db_session
    # Override get_scheduler
    fastapi_app.dependency_overrides[original_get_scheduler] = lambda: mock_scheduler
    # Explicitly override get_metadata_store to use the test session
    sql_store_for_api = SqlMetadataStore(session=db_session)
    fastapi_app.dependency_overrides[original_get_metadata_store] = lambda: sql_store_for_api

    # Use httpx.AsyncClient with ASGITransport
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    # Clean up overrides
    fastapi_app.dependency_overrides = {}


# --- Test Cases ---

# Note: Tests interacting with DB need the db_session fixture for setup/cleanup.
# Scheduler mocking is handled by the async_test_client fixture override.
@pytest.mark.asyncio # Mark as async
async def test_create_task_success(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    mock_scheduler: AsyncMock, # Inject mock scheduler to check calls
    db_session: AsyncSession # Keep db_session if needed for verification (though not strictly needed here)
):
    """
    Test successful task creation via POST /tasks/.
    Dependencies overridden in async_test_client fixture.
    """
    # Arrange
    # Arrange
    mock_scheduler.reset_mock() # Reset mock before use
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    expected_task_id = "new_task_123"
    # Configure mock scheduler return value (ensure it's awaitable if needed)
    mock_scheduler.submit_task.return_value = Task(
        task_id=expected_task_id,
        task_type=task_data["task_type"],
        status=TaskStatus.PENDING,
        input_data=task_data["input_data"],
        created_at=datetime.now(timezone.utc), # Corrected indentation
        updated_at=datetime.now(timezone.utc), # Corrected indentation
    )

    # Act
    response = await async_test_client.post("/api/v1/tasks/", json=task_data) # Use await

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


@pytest.mark.asyncio # Mark as async
async def test_create_task_scheduler_error(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    mock_scheduler: AsyncMock # Inject mock scheduler
):
    """
    Test task creation failure when scheduler raises an exception.
    """
    # Arrange
    mock_scheduler.reset_mock() # Reset mock before use
    task_data = {"task_type": "agent_run", "input_data": {"prompt": "hello"}}
    mock_scheduler.submit_task.side_effect = Exception("Scheduler boom!") # Ensure side effect is set

    # Act
    response = await async_test_client.post("/api/v1/tasks/", json=task_data) # Use await

    # Assert
    assert response.status_code == 500
    assert "Failed to submit task: Scheduler boom!" in response.json()["detail"]
    mock_scheduler.submit_task.assert_awaited_once() # Check it was called


@pytest.mark.asyncio
async def test_get_task_success(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession
):
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
    await db_session.commit()
    # No need to close session here, fixture manages it

    # Act
    response = await async_test_client.get(f"/api/v1/tasks/{task_id}") # Use await

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["task_id"] == task_id
    assert response_data["task_type"] == db_task.task_type
    assert response_data["status"] == TaskStatus.RUNNING.value
    assert response_data["input_data"] == db_task.input_data
    assert response_data["started_at"] is not None


@pytest.mark.asyncio
async def test_get_task_not_found(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession
):
    """
    Test retrieval of a non-existent task via GET /tasks/{task_id} using real DB.
    """
    # Arrange
    task_id = "non_existent_task_db"
    # Ensure task does not exist (db_session fixture handles cleanup)
    # No need to close session

    # Act
    response = await async_test_client.get(f"/api/v1/tasks/{task_id}") # Use await

    # Assert
    assert response.status_code == 404 # Expect 404 if endpoint handles TaskNotFoundError
    assert response.json()["detail"] == f"Task with ID '{task_id}' not found."


@pytest.mark.asyncio
async def test_get_task_metadata_store_error(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession,
    mocker
):
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
    # Patch the get_task method on the SqlMetadataStore class used by the dependency override
    # Note: Patching the class method, not an instance
    mocker.patch("ops_core.metadata.sql_store.SqlMetadataStore.get_task", side_effect=Exception(error_message), autospec=True)
    # No need to close session

    # Act
    response = await async_test_client.get(f"/api/v1/tasks/{task_id}") # Use await

    # Assert
    assert response.status_code == 500
    assert "Failed to retrieve task" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_tasks_success_empty(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession
):
    """
    Test successful listing of tasks when none exist via GET /tasks/ using real DB.
    """
    # Arrange (Ensure DB is empty - handled by fixture)
    # No need to close session

    # Act
    response = await async_test_client.get("/api/v1/tasks/") # Use await

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["tasks"] == []
    assert response_data["total"] == 0


@pytest.mark.asyncio
async def test_list_tasks_success_with_data(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession
):
    """
    Test successful listing of tasks when some exist via GET /tasks/ using real DB.
    """
    # Arrange: Create tasks directly in the DB
    now = datetime.now(timezone.utc)
    task1 = Task(task_id="db_task1", name="DB Task 1", task_type="typeA", status=TaskStatus.COMPLETED, input_data={}, created_at=now, updated_at=now)
    task2 = Task(task_id="db_task2", name="DB Task 2", task_type="typeB", status=TaskStatus.PENDING, input_data={}, created_at=now, updated_at=now)
    db_session.add_all([task1, task2])
    await db_session.commit()
    # No need to close session

    # Act
    response = await async_test_client.get("/api/v1/tasks/") # Use await

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
async def test_list_tasks_metadata_store_error(
    async_test_client: httpx.AsyncClient, # Use new client fixture
    db_session: AsyncSession,
    mocker
):
    """
    Test listing failure when metadata store raises an exception (simulated DB error).
    """
    # Arrange
    error_message = "Simulated failed to query tasks"
    # Patch the list_tasks method on the SqlMetadataStore class used by the dependency override
    mocker.patch("ops_core.metadata.sql_store.SqlMetadataStore.list_tasks", side_effect=Exception(error_message), autospec=True)
    # No need to close session

    # Act
    response = await async_test_client.get("/api/v1/tasks/") # Use await

    # Assert
    assert response.status_code == 500
    assert f"Failed to list tasks" in response.json()["detail"]


# --- Input Validation Tests ---

# These tests don't interact with the store/scheduler, so they don't need db_session or overrides
# They can use the async client, but don't strictly need to be async tests
@pytest.mark.asyncio
async def test_create_task_missing_task_type(async_test_client: httpx.AsyncClient):
    """
    Test task creation with missing 'task_type' field.
    """
    # Arrange
    invalid_task_data = {"input_data": {"prompt": "hello"}} # Missing task_type

    # Act
    response = await async_test_client.post("/api/v1/tasks/", json=invalid_task_data) # Use await

    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    assert any(err["msg"] == "Field required" and "task_type" in err["loc"] for err in response_data["detail"])

@pytest.mark.asyncio
async def test_create_task_invalid_input_data_type(async_test_client: httpx.AsyncClient):
    """
    Test task creation with invalid type for 'input_data' (should be dict).
    """
    # Arrange
    invalid_task_data = {"task_type": "agent_run", "input_data": "not_a_dictionary"}

    # Act
    response = await async_test_client.post("/api/v1/tasks/", json=invalid_task_data) # Use await

    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    # Pydantic v2 message for wrong type
    assert any("Input should be a valid dictionary" in err["msg"] and "input_data" in err["loc"] for err in response_data["detail"])


# TODO: Add more specific input validation tests if TaskCreateRequest schema becomes stricter
# TODO: Add tests for pagination if implemented in list_tasks
