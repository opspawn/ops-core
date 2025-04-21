"""
Pytest configuration and shared fixtures for Ops-Core tests.
"""

import pytest
import sys
import os
import logging # Import the logging module
import redis.asyncio as redis # Import redis async client
from typing import AsyncGenerator # Import AsyncGenerator
import httpx # Import httpx module

# Configure basic logging for fixtures
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get a logger instance for this module

# Ensure the opscore package is discoverable
# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import from opscore
try:
    from opscore import storage, workflow, models # Add workflow import
    from datetime import datetime
    from pydantic import HttpUrl
except ImportError as e:
    print(f"Error importing opscore modules in conftest.py: {e}")
    print(f"Project root added to path: {project_root}")
    print(f"Current sys.path: {sys.path}")
    # Re-raise the exception to make it clear there's an issue
    raise

@pytest.fixture() # Removed autouse=True
def clear_storage_before_each_test():
    """
    Fixture to clear the in-memory storage and task queue before tests.
    Should be explicitly used with @pytest.mark.usefixtures where needed.
    """
    print("\nClearing storage and queue before test...") # Added print for visibility
    storage.clear_all_data()
    # Clear the in-memory deque directly (specific to current implementation)
    if hasattr(workflow, '_task_queue'):
        workflow._task_queue.clear()
    yield # Test runs here
    print("Storage and queue cleared after test.") # Optional: confirm cleanup

# --- Sample Data Fixtures ---

@pytest.fixture(scope="session") # Session scope as these are read-only data
def valid_agent_reg_details_data() -> dict:
    """Provides valid raw data for AgentRegistrationDetails."""
    return {
        "agentId": "agent_test_123", # Added missing agentId
        "agentName": "TestAgent",
        "version": "1.0.1",
        "capabilities": ["test_capability", "another_one"],
        "contactEndpoint": "http://localhost:9000/testagent",
        "metadata": {"host": "testhost", "pid": 1234}
    }

@pytest.fixture(scope="session")
def valid_agent_reg_details(valid_agent_reg_details_data) -> models.AgentRegistrationDetails:
    """Provides a valid AgentRegistrationDetails model instance."""
    return models.AgentRegistrationDetails(**valid_agent_reg_details_data)

@pytest.fixture(scope="session")
def valid_agent_info(valid_agent_reg_details) -> models.AgentInfo:
    """Provides a valid AgentInfo model instance."""
    return models.AgentInfo(
        **valid_agent_reg_details.model_dump(),
        # agentId="agent_test_123", # Removed redundant agentId kwarg
        registrationTime=datetime(2024, 1, 1, 12, 0, 0) # Fixed time for predictability
    )

@pytest.fixture(scope="session")
def valid_agent_state_data() -> dict:
    """Provides valid raw data for AgentState."""
    return {
        "agentId": "agent_test_123",
        "state": "idle",
        "details": {"reason": "completed task xyz"},
        "timestamp": datetime(2024, 1, 1, 12, 5, 0) # Fixed time
    }

@pytest.fixture(scope="session")
def valid_agent_state(valid_agent_state_data) -> models.AgentState:
    """Provides a valid AgentState model instance."""
    return models.AgentState(**valid_agent_state_data)


@pytest.fixture(scope="session")
def valid_workflow_def_dict() -> dict:
    """Provides a dictionary representing a valid workflow definition."""
    return {
        "id": "wf_test_001",
        "name": "Test Workflow",
        "description": "A simple workflow for testing.",
        "version": "1.1",
        "tasks": [
            {"taskId": "task_A", "name": "First Task", "agentCapability": "cap_A", "parameters": {"p1": "v1"}, "nextTaskId": "task_B"},
            {"taskId": "task_B", "name": "Second Task", "agentCapability": "cap_B", "parameters": {"p2": "v2"}, "nextTaskId": None}
        ]
    }

@pytest.fixture(scope="session")
def valid_workflow_def_model(valid_workflow_def_dict) -> models.WorkflowDefinition:
    """Provides a valid WorkflowDefinition model instance."""
    return models.WorkflowDefinition(**valid_workflow_def_dict)

@pytest.fixture(scope="function") # Function scope as ID is generated dynamically
def valid_session_model() -> models.WorkflowSession:
    """Provides a valid WorkflowSession model instance."""
    # Note: sessionId, startTime, last_updated_time are auto-generated
    return models.WorkflowSession(
        workflowId="wf_test_001",
        agentId="agent_test_123",
        status="started"
    )

@pytest.fixture(scope="session")
def valid_task_data_dict() -> dict:
    """Provides a dictionary representing valid data for models.Task."""
    return {
        "taskId": "task_instance_abc",
        "workflowId": "wf_test_001",
        "sessionId": "session_xyz",
        "agentId": "agent_test_123",
        "taskDefinitionId": "task_A",
        "payload": {"p1": "v1_override"},
        "status": "pending",
        "retryCount": 0,
        "maxRetries": 2
        # createdAt, updatedAt are auto-generated
    }

# Add more fixtures as needed

# --- FastAPI Test Client Fixture ---

import pytest_asyncio # Use pytest_asyncio for async fixtures
from httpx import AsyncClient
from fastapi import FastAPI
from opscore.api import app as fastapi_app # Import the app instance

@pytest_asyncio.fixture(scope="function") # Function scope for isolation
async def test_client(clear_storage_before_each_test) -> AsyncClient: # Ensure storage is cleared
    """
    Provides an asynchronous test client for the FastAPI application.
    """
    # Use 'async with' for proper client setup and teardown
    async with AsyncClient(app=fastapi_app, base_url="http://testserver") as client:
        yield client # Provide the client to the test function

# --- Redis Fixtures for Integration Tests ---

@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """
    Provides an asynchronous Redis client connected to the test Redis instance.
    Connection details are read from environment variables (matching docker-compose).
    """
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    logger.info(f"Connecting Redis client to {redis_host}:{redis_port}")
    client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        # Ping to ensure connection is working
        await client.ping()
        logger.info("Redis client connected successfully.")
        yield client
    except redis.RedisError as e:
        logger.error(f"Failed to connect to Redis at {redis_host}:{redis_port}: {e}", exc_info=True)
        pytest.fail(f"Could not connect to Redis at {redis_host}:{redis_port}: {e}")
    finally:
        # Ensure the client is closed after the test
        await client.aclose() # Use aclose() for async client
        logger.info("Redis client connection closed.")

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clear_redis_before_each_test(request, redis_client):
    """
    Fixture to clear the Redis database before each test function.
    This fixture is autoused for async tests.
    """
    # Only clear Redis if the test is marked to use Redis storage
    # We can use a marker or check environment variables, but for now,
    # let's assume this fixture is applied only where needed (e.g., integration tests).
    # A simpler approach for now is to just clear if the redis_client fixture is requested.
    # Pytest's fixture resolution handles this dependency.

    logger.info("Clearing Redis database before test...")
    try:
        await redis_client.flushdb()
    except redis.RedisError as e:
        logger.error(f"Failed to clear Redis database: {e}", exc_info=True)
        pytest.fail(f"Could not clear Redis database: {e}")

    yield # Test runs here

    logger.info("Redis database cleanup complete after test.")

# Note: The original clear_storage_before_each_test fixture remains but is not autoused.
# It should be explicitly applied to unit tests that rely on in-memory storage.
# Integration tests using Redis will implicitly use clear_redis_before_each_test
# via the dependency on redis_client (if the test function requests redis_client).
# However, for clarity and to ensure cleanup even if redis_client isn't directly requested
# by the test function, we can make clear_redis_before_each_test autouse=True
# and potentially add a marker check if needed later for more fine-grained control.
# For now, autouse=True on clear_redis_before_each_test is simpler for the integration test suite.

# Need to import redis.asyncio
# from opscore import storage, workflow, models # Already imported
# from datetime import datetime # Already imported
# from pydantic import HttpUrl # Already imported
# import os # Already imported
# import redis.asyncio as redis # Need to import redis.asyncio here

@pytest_asyncio.fixture(scope="function") # Change scope to function
async def opscore_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for interacting with the Ops-Core service."""
    """HTTP client for interacting with the Ops-Core service."""
    # Temporarily hardcode API key to unblock debugging
    opscore_api_key = "test-api-key"
    print(f"opscore_client fixture: Using hardcoded API Key '{opscore_api_key}'.") # Added print statement for verification
    # Use Authorization: Bearer <key> format as required by Ops-Core API
    headers = {"Authorization": f"Bearer {opscore_api_key}"}
    async with httpx.AsyncClient(base_url=OPSCORE_BASE_URL, timeout=30.0, headers=headers) as client:
        yield client

@pytest_asyncio.fixture(scope="function") # Change scope to function
async def agentkit_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for interacting with the AgentKit service."""
    async with httpx.AsyncClient(base_url=AGENTKIT_BASE_URL, timeout=30.0) as client:
        yield client