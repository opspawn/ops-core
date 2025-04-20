"""
Unit tests for the Ops-Core SDK clients.
"""

import pytest
import httpx
from pytest_httpx import HTTPXMock
from datetime import datetime, timezone

from opscore_sdk.client import OpsCoreClientSync, OpsCoreClientAsync
from opscore_sdk.exceptions import OpsCoreApiError, AuthenticationError, NotFoundError, ConnectionError, OpsCoreSDKError
from opscore_sdk.models import AgentStateResponse, WorkflowTriggerResponse

# --- Constants for Tests ---
BASE_URL = "http://test-opscore.local"
API_KEY = "test-sdk-key"
AGENT_ID = "agent-sdk-test-123"
WORKFLOW_ID = "wf-sdk-test-abc"
SESSION_ID = "sess-sdk-test-xyz"

# --- Fixtures ---

@pytest.fixture
def sync_client() -> OpsCoreClientSync:
    """Provides a synchronous client instance."""
    client = OpsCoreClientSync(base_url=BASE_URL, api_key=API_KEY)
    yield client
    client.close() # Ensure client is closed after test

# Use addfinalizer with event_loop to handle async cleanup
@pytest.fixture
def async_client(request, event_loop) -> OpsCoreClientAsync: # Add event_loop fixture
    """Provides an asynchronous client instance."""
    client = OpsCoreClientAsync(base_url=BASE_URL, api_key=API_KEY)

    def cleanup():
        # Run the async close in the event loop used by the test
        # Note: This assumes the default loop scope or function scope.
        # If loop scope changes, this might need adjustment.
        event_loop.run_until_complete(client.close())

    request.addfinalizer(cleanup) # Register the synchronous cleanup function
    return client # Return the client instance directly

# --- Synchronous Client Tests ---

def test_sync_client_init_errors():
    """Test initialization errors for the sync client."""
    with pytest.raises(ValueError, match="base_url cannot be empty"):
        OpsCoreClientSync(base_url="", api_key=API_KEY)
    with pytest.raises(ValueError, match="api_key cannot be empty"):
        OpsCoreClientSync(base_url=BASE_URL, api_key="")

def test_sync_update_state_success(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test successful state update using the sync client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"

    httpx_mock.add_response(
        url=expected_url,
        method="POST",
        status_code=202, # Expected success status
        json={"status": "success", "message": "State update accepted"} # Example response body
    )

    sync_client.update_state(agent_id=AGENT_ID, state="active", details={"task": "testing"})

    # Verify the request was made correctly
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == "POST"
    assert str(request.url) == expected_url
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    request_data = request.read().decode()
    assert '"agentId": "' + AGENT_ID + '"' in request_data
    assert '"state": "active"' in request_data
    assert '"task": "testing"' in request_data
    assert '"timestamp":' in request_data # Check timestamp was added

def test_sync_get_state_success(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test successful state retrieval using the sync client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    timestamp_str = datetime.now(timezone.utc).isoformat()
    mock_response: AgentStateResponse = {
        "agentId": AGENT_ID,
        "state": "idle",
        "details": {"last_task": "completed"},
        "timestamp": timestamp_str
    }

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        status_code=200,
        json=mock_response
    )

    state = sync_client.get_state(agent_id=AGENT_ID)

    assert state == mock_response
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == "GET"
    assert str(request.url) == expected_url
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"

def test_sync_trigger_workflow_success(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test successful workflow trigger using the sync client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/workflow"
    expected_url = f"{BASE_URL}{endpoint}"
    mock_response: WorkflowTriggerResponse = {
        "sessionId": SESSION_ID,
        "workflowId": WORKFLOW_ID,
        "message": "Workflow triggered successfully"
    }

    httpx_mock.add_response(
        url=expected_url,
        method="POST",
        status_code=202,
        json=mock_response
    )

    response = sync_client.trigger_workflow(
        agent_id=AGENT_ID,
        workflow_definition_id=WORKFLOW_ID,
        initial_payload={"input": "data"}
    )

    assert response == mock_response
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == "POST"
    assert str(request.url) == expected_url
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    request_data = request.read().decode()
    assert '"workflowDefinitionId": "' + WORKFLOW_ID + '"' in request_data
    assert '"input": "data"' in request_data

def test_sync_api_error_not_found(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test 404 Not Found error handling."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    error_detail = {"detail": f"Agent {AGENT_ID} not found"}

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        status_code=404,
        json=error_detail
    )

    with pytest.raises(NotFoundError) as excinfo:
        sync_client.get_state(agent_id=AGENT_ID)

    assert excinfo.value.status_code == 404
    assert str(AGENT_ID) in str(excinfo.value.detail) # Check detail propagation

def test_sync_api_error_auth(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test 401 Unauthorized error handling."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    error_detail = {"detail": "Invalid authentication credentials"}

    httpx_mock.add_response(
        url=expected_url,
        method="POST",
        status_code=401,
        json=error_detail
    )

    with pytest.raises(AuthenticationError) as excinfo:
        sync_client.update_state(agent_id=AGENT_ID, state="error")

    assert excinfo.value.status_code == 401
    assert "Invalid authentication credentials" in str(excinfo.value.detail)

def test_sync_api_error_generic(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test generic API error handling (e.g., 500)."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/workflow"
    expected_url = f"{BASE_URL}{endpoint}"
    error_detail = {"detail": "Internal server error"}

    httpx_mock.add_response(
        url=expected_url,
        method="POST",
        status_code=500,
        json=error_detail
    )

    with pytest.raises(OpsCoreApiError) as excinfo:
        sync_client.trigger_workflow(agent_id=AGENT_ID, workflow_definition_id=WORKFLOW_ID)

    assert excinfo.value.status_code == 500
    assert "Internal server error" in str(excinfo.value.detail)
    assert not isinstance(excinfo.value, AuthenticationError) # Ensure it's not misclassified
    assert not isinstance(excinfo.value, NotFoundError)

def test_sync_connection_error(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test handling of connection errors."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"

    httpx_mock.add_exception(httpx.ConnectError("Failed to connect"))

    with pytest.raises(ConnectionError, match="HTTP request failed: Failed to connect"):
        sync_client.get_state(agent_id=AGENT_ID)

def test_sync_timeout_error(sync_client: OpsCoreClientSync, httpx_mock: HTTPXMock):
    """Test handling of timeout errors."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"

    httpx_mock.add_exception(httpx.TimeoutException("Request timed out"))

    with pytest.raises(ConnectionError, match="Request timed out"):
        sync_client.get_state(agent_id=AGENT_ID)

def test_sync_client_context_manager(httpx_mock: HTTPXMock):
    """Test using the sync client as a context manager."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    timestamp_str = datetime.now(timezone.utc).isoformat()
    mock_response: AgentStateResponse = {
        "agentId": AGENT_ID, "state": "idle", "details": None, "timestamp": timestamp_str
    }
    httpx_mock.add_response(url=expected_url, method="GET", status_code=200, json=mock_response)

    with OpsCoreClientSync(base_url=BASE_URL, api_key=API_KEY) as client:
        state = client.get_state(agent_id=AGENT_ID)
        assert state == mock_response
    # Client should be closed automatically here

# --- Asynchronous Client Tests ---

@pytest.mark.asyncio
async def test_async_client_init_errors():
    """Test initialization errors for the async client."""
    with pytest.raises(ValueError, match="base_url cannot be empty"):
        OpsCoreClientAsync(base_url="", api_key=API_KEY)
    with pytest.raises(ValueError, match="api_key cannot be empty"):
        OpsCoreClientAsync(base_url=BASE_URL, api_key="")

@pytest.mark.asyncio
async def test_async_update_state_success(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test successful state update using the async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"

    httpx_mock.add_response(url=expected_url, method="POST", status_code=202)

    await async_client.update_state(agent_id=AGENT_ID, state="active", details={"task": "async testing"})

    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == "POST"
    assert str(request.url) == expected_url
    request_data = request.read().decode()
    assert '"state": "active"' in request_data
    assert '"task": "async testing"' in request_data

@pytest.mark.asyncio
async def test_async_get_state_success(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test successful state retrieval using the async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    timestamp_str = datetime.now(timezone.utc).isoformat()
    mock_response: AgentStateResponse = {
        "agentId": AGENT_ID, "state": "idle", "details": None, "timestamp": timestamp_str
    }

    httpx_mock.add_response(url=expected_url, method="GET", status_code=200, json=mock_response)

    state = await async_client.get_state(agent_id=AGENT_ID)
    assert state == mock_response

@pytest.mark.asyncio
async def test_async_trigger_workflow_success(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test successful workflow trigger using the async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/workflow"
    expected_url = f"{BASE_URL}{endpoint}"
    mock_response: WorkflowTriggerResponse = {
        "sessionId": SESSION_ID, "workflowId": WORKFLOW_ID, "message": "Async trigger OK"
    }

    httpx_mock.add_response(url=expected_url, method="POST", status_code=202, json=mock_response)

    response = await async_client.trigger_workflow(
        agent_id=AGENT_ID,
        workflow_definition_id=WORKFLOW_ID,
        initial_payload={"input": "async data"}
    )
    assert response == mock_response

@pytest.mark.asyncio
async def test_async_api_error_not_found(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test 404 Not Found error handling in async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    httpx_mock.add_response(url=expected_url, method="GET", status_code=404, json={"detail": "Not here"})

    with pytest.raises(NotFoundError) as excinfo:
        await async_client.get_state(agent_id=AGENT_ID)
    assert excinfo.value.status_code == 404

@pytest.mark.asyncio
async def test_async_api_error_auth(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test 401 Unauthorized error handling in async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    httpx_mock.add_response(url=expected_url, method="POST", status_code=401, json={"detail": "Bad key"})

    with pytest.raises(AuthenticationError) as excinfo:
        await async_client.update_state(agent_id=AGENT_ID, state="error")
    assert excinfo.value.status_code == 401

@pytest.mark.asyncio
async def test_async_connection_error(async_client: OpsCoreClientAsync, httpx_mock: HTTPXMock):
    """Test handling of connection errors in async client."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    httpx_mock.add_exception(httpx.ConnectError("Async connection failed"))

    with pytest.raises(ConnectionError, match="Async connection failed"):
        await async_client.get_state(agent_id=AGENT_ID)

@pytest.mark.asyncio
async def test_async_client_context_manager(httpx_mock: HTTPXMock):
    """Test using the async client as a context manager."""
    endpoint = f"/v1/opscore/agent/{AGENT_ID}/state"
    expected_url = f"{BASE_URL}{endpoint}"
    timestamp_str = datetime.now(timezone.utc).isoformat()
    mock_response: AgentStateResponse = {
        "agentId": AGENT_ID, "state": "idle", "details": None, "timestamp": timestamp_str
    }
    httpx_mock.add_response(url=expected_url, method="GET", status_code=200, json=mock_response)

    async with OpsCoreClientAsync(base_url=BASE_URL, api_key=API_KEY) as client:
        state = await client.get_state(agent_id=AGENT_ID)
        assert state == mock_response
    # Client should be closed automatically here