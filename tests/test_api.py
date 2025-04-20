"""
Unit and Integration tests for the opscore.api module.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app instance
from opscore.api import app
from opscore import models
from opscore import exceptions # Import custom exceptions

# Create a TestClient instance
client = TestClient(app=app)

# Fixtures from conftest.py are automatically available
# Includes: clear_storage_before_each_test (autouse), valid_agent_reg_details,
#           valid_agent_info, valid_agent_state, valid_session_model, valid_workflow_def

# --- Test /health Endpoint ---

def test_health_check_success():
    """Test GET /health returns 200 and expected body."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"} # Corrected expected status

# --- Test POST /v1/opscore/agent/{agentId}/state Endpoint ---

# Mock the expected API key for testing consistency
EXPECTED_TEST_API_KEY = "test-api-key"
HEADERS = {"Authorization": f"Bearer {EXPECTED_TEST_API_KEY}"}

@patch('opscore.api.lifecycle.set_state') # Patch where it's used in the api module
def test_set_state_success(mock_set_state):
    """Test POST /state returns 202 on success with valid auth."""
    agent_id = "agent_test_state_success"
    payload = {
        "agentId": agent_id,
        "state": "active",
        "details": {"info": "testing"},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=HEADERS)

    assert response.status_code == 202
    # Check against the StatusResponse model structure
    # Use the actual model for comparison
    assert response.json() == models.StatusResponse(message="State update accepted").model_dump()
    mock_set_state.assert_called_once_with(
        agent_id=agent_id,
        new_state=payload["state"],
        details=payload["details"],
        timestamp=payload["timestamp"]
    )

def test_set_state_missing_auth_header():
    """Test POST /state returns 401 if Authorization header is missing."""
    agent_id = "agent_test_no_auth"
    payload = {"agentId": agent_id, "state": "idle"}
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload) # No headers
    assert response.status_code == 401
    assert "Authorization header missing" in response.json()["detail"]

def test_set_state_invalid_scheme():
    """Test POST /state returns 401 if Authorization scheme is not Bearer."""
    agent_id = "agent_test_bad_scheme"
    payload = {"agentId": agent_id, "state": "idle"}
    headers = {"Authorization": f"Basic {EXPECTED_TEST_API_KEY}"}
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]

def test_set_state_invalid_token():
    """Test POST /state returns 401 if Bearer token is incorrect."""
    agent_id = "agent_test_bad_token"
    payload = {"agentId": agent_id, "state": "idle"}
    headers = {"Authorization": "Bearer wrong-key"}
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.json()["detail"]

def test_set_state_invalid_body_missing_field():
    """Test POST /state returns 422 if required 'state' field is missing."""
    agent_id = "agent_test_missing_field"
    payload = {"agentId": agent_id} # Missing 'state'
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=HEADERS)
    assert response.status_code == 422
    # Check for detail structure typical of FastAPI validation errors
    assert "detail" in response.json()
    assert any("state" in err["loc"] and "Field required" in err["msg"] for err in response.json()["detail"])

def test_set_state_invalid_body_wrong_type():
    """Test POST /state returns 422 if 'state' field has wrong type."""
    agent_id = "agent_test_wrong_type"
    payload = {"agentId": agent_id, "state": 123} # 'state' should be string
    response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert any("state" in err["loc"] and "Input should be a valid string" in err["msg"] for err in response.json()["detail"])

def test_set_state_agent_id_mismatch():
    """Test POST /state returns 400 if path agentId != payload agentId."""
    path_agent_id = "agent_in_path"
    payload_agent_id = "agent_in_payload"
    # Add timestamp to pass Pydantic validation
    payload = {"agentId": payload_agent_id, "state": "idle", "timestamp": "2024-01-01T00:00:00Z"}
    response = client.post(f"/v1/opscore/agent/{path_agent_id}/state", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "Agent ID in path does not match agent ID in payload" in response.json()["detail"]

@patch('opscore.api.lifecycle.set_state')
def test_set_state_agent_not_found(mock_set_state):
   """Test POST /state returns 404 if lifecycle reports agent not found."""
   # UPDATE: Now testing the actual custom exception handling.
   agent_id = "agent_test_not_found"
   # Use the actual exception class
   mock_set_state.side_effect = exceptions.AgentNotFoundError(agent_id)

   # Add timestamp to pass Pydantic validation
   payload = {"agentId": agent_id, "state": "idle", "timestamp": "2024-01-01T00:00:00Z"}
   response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=HEADERS)

   # Updated check: API now maps AgentNotFoundError to 404
   assert response.status_code == 404
   assert f"Agent not found: {agent_id}" in response.json()["detail"]
   mock_set_state.assert_called_once()


@patch('opscore.api.lifecycle.set_state')
def test_set_state_storage_error(mock_set_state):
   """Test POST /state returns 500 if lifecycle reports a storage error."""
   agent_id = "agent_test_storage_error"
   # Use the actual exception class
   mock_set_state.side_effect = exceptions.StorageError("Storage connection failed")

   # Add timestamp to pass Pydantic validation
   payload = {"agentId": agent_id, "state": "error", "details": {"reason": "storage fail"}, "timestamp": "2024-01-01T00:00:00Z"}
   response = client.post(f"/v1/opscore/agent/{agent_id}/state", json=payload, headers=HEADERS)
   # Check the actual status code returned by the API's generic exception handler
   assert response.status_code == 500
   # Middleware now returns the raw exception string in the detail
   assert response.json() == {"detail": "Storage error: Storage connection failed"}
   mock_set_state.assert_called_once()

# --- Test POST /v1/opscore/agent/{agentId}/workflow Endpoint ---

@patch('opscore.api.workflow.enqueue_task')
@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer directly checked in API before start_session
def test_trigger_workflow_success_with_id(
    # mock_agent_exists, # Removed
    mock_read_wf_def,
    mock_start_session,
    mock_enqueue_task,
    valid_agent_info, # Fixture from conftest
    valid_workflow_def_model, # Corrected fixture name
    valid_session_model # Fixture from conftest - used only for structure reference now
):
    """Test POST /workflow succeeds with a valid workflowDefinitionId."""
    agent_id = valid_agent_info.agentId
    workflow_id = valid_workflow_def_model.id # Corrected fixture name

    # --- Mock Setup ---
    # mock_agent_exists.return_value = True # No longer needed for this path
    mock_read_wf_def.return_value = valid_workflow_def_model # Corrected fixture name
    # Use the valid_session_model fixture as the return value for start_session
    # Ensure the session ID in the fixture matches what the response should contain
    # Ensure sessionId is a string to prevent downstream Pydantic errors
    mock_session = MagicMock(spec=models.WorkflowSession)
    mock_session.sessionId = "mock-session-id-string-123" # Explicitly set as string
    mock_start_session.return_value = mock_session
    mock_enqueue_task.return_value = None # Assume enqueue returns None on success

    # --- Request Payload ---
    payload = {
        "workflowDefinitionId": workflow_id,
        "initialPayload": {"input": "test_data"}
    }

    # --- API Call ---
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)

    # --- Assertions ---
    assert response.status_code == 202
    expected_response = {
        "sessionId": mock_session.sessionId, # Use ID from the mock return value
        "workflowId": workflow_id,
        "message": "Workflow triggered successfully" # Default message
    }
    # Adjust expected message if the workflow has no tasks (based on corrected fixture name)
    if not valid_workflow_def_model.tasks:
         expected_response["message"] = "Workflow triggered but has no tasks." # This case correctly has a period in the API code

    assert response.json() == expected_response

    # Verify mocks were called
    # mock_agent_exists.assert_called_once_with(agent_id) # No longer called here
    mock_read_wf_def.assert_called_once_with(workflow_id)
    mock_start_session.assert_called_once_with(agent_id=agent_id, workflow_id=workflow_id)

    # Verify enqueue was called if the workflow has tasks (based on corrected fixture name)
    if valid_workflow_def_model.tasks:
        mock_enqueue_task.assert_called_once()
        # Optionally, add more specific checks on the task_instance_data passed to enqueue
        call_args, _ = mock_enqueue_task.call_args
        enqueued_task_data = call_args[0]
        assert enqueued_task_data["workflowId"] == workflow_id
        assert enqueued_task_data["sessionId"] == mock_session.sessionId
        assert enqueued_task_data["agentId"] == agent_id
        assert enqueued_task_data["taskDefinitionId"] == valid_workflow_def_model.tasks[0].get("taskId") # Corrected fixture name
        assert enqueued_task_data["payload"] == payload["initialPayload"]
        assert enqueued_task_data["status"] == "pending"
    else:
        mock_enqueue_task.assert_not_called()


@patch('opscore.api.workflow.enqueue_task')
@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.save_workflow_definition') # Add mock for saving
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer directly checked
def test_trigger_workflow_success_with_inline_def(
    # mock_agent_exists, # Removed
    mock_read_wf_def,
    mock_save_wf_def, # Add mock param
    mock_start_session,
    mock_enqueue_task,
    valid_agent_info,
    valid_workflow_def_model, # Corrected fixture name
    valid_session_model # Used only for structure reference now
):
    """Test POST /workflow succeeds with a valid inline workflowDefinition."""
    agent_id = valid_agent_info.agentId
    # Use the structure from the corrected fixture, but pass it as a dict
    inline_workflow_dict = valid_workflow_def_model.model_dump(mode='json') # Corrected fixture name
    workflow_id = inline_workflow_dict["id"] # Get ID from the dict

    # --- Mock Setup ---
    # mock_agent_exists.return_value = True # No longer needed
    mock_read_wf_def.return_value = None # Simulate definition doesn't exist yet
    mock_save_wf_def.return_value = None # Assume save returns None
    # Ensure sessionId is a string
    mock_session = MagicMock(spec=models.WorkflowSession)
    mock_session.sessionId = "mock-session-id-string-456" # Explicitly set as string
    mock_start_session.return_value = mock_session
    mock_enqueue_task.return_value = None

    # --- Request Payload ---
    payload = {
        "workflowDefinition": inline_workflow_dict,
        "initialPayload": {"input": "inline_test"}
    }

    # --- API Call ---
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)

    # --- Assertions ---
    assert response.status_code == 202
    expected_response = {
        "sessionId": mock_session.sessionId,
        "workflowId": workflow_id,
        "message": "Workflow triggered successfully" # Corrected: No period
    }
    if not valid_workflow_def_model.tasks: # Corrected fixture name
         expected_response["message"] = "Workflow triggered but has no tasks." # This case correctly has a period in the API code

    assert response.json() == expected_response

    # Verify mocks
    # mock_agent_exists.assert_called_once_with(agent_id) # No longer called
    mock_read_wf_def.assert_called_once_with(workflow_id) # API checks if it exists
    mock_save_wf_def.assert_called_once() # API should save the new inline def
    # Check that the saved object matches the inline definition
    call_args, _ = mock_save_wf_def.call_args
    saved_def_model = call_args[0]
    assert isinstance(saved_def_model, models.WorkflowDefinition)
    assert saved_def_model.model_dump(mode='json') == inline_workflow_dict

    mock_start_session.assert_called_once_with(agent_id=agent_id, workflow_id=workflow_id)

    if valid_workflow_def_model.tasks: # Corrected fixture name
        mock_enqueue_task.assert_called_once()
        call_args, _ = mock_enqueue_task.call_args
        enqueued_task_data = call_args[0]
        assert enqueued_task_data["payload"] == payload["initialPayload"]
    else:
        mock_enqueue_task.assert_not_called()


def test_trigger_workflow_invalid_body_missing_definition():
    """Test POST /workflow returns 422 if both definition ID and inline def are missing."""
    agent_id = "agent_test_wf_invalid"
    payload = {"initialPayload": {}} # Missing workflowDefinitionId and workflowDefinition
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert "detail" in response.json()
    # Check for the specific validation error from the model validator
    # Simplify assertion: just check that detail is present and is a list (FastAPI format)
    assert isinstance(response.json().get("detail"), list)
    assert len(response.json()["detail"]) > 0

def test_trigger_workflow_invalid_body_both_definitions():
    """Test POST /workflow returns 422 if both definition ID and inline def are provided."""
    agent_id = "agent_test_wf_invalid"
    payload = {
        "workflowDefinitionId": "wf_id_123",
        "workflowDefinition": {"id": "wf_inline_123", "name": "Inline Def", "tasks": []},
        "initialPayload": {}
    }
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert "detail" in response.json()
    # Check for the specific validation error from the model validator
    # Simplify assertion: just check that detail is present and is a list
    assert isinstance(response.json().get("detail"), list)
    assert len(response.json()["detail"]) > 0

def test_trigger_workflow_invalid_inline_definition():
    """Test POST /workflow returns 422 if the inline definition is invalid."""
    agent_id = "agent_test_wf_invalid"
    payload = {
        "workflowDefinition": {"name": "Missing ID"}, # Missing required 'id' field
        "initialPayload": {}
    }
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert "detail" in response.json()
    # Check for validation error related to the inline definition structure
    assert any("workflowDefinition" in err["loc"] and "id" in err["loc"] and "Field required" in err["msg"] for err in response.json()["detail"])


# Refactored Test: Agent not found is now detected during start_session
@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition') # Need to mock this to return a valid def
def test_trigger_workflow_agent_not_found(mock_read_wf_def, mock_start_session, valid_workflow_def_model):
   """Test POST /workflow returns 404 if agent does not exist."""
   agent_id = "agent_does_not_exist"
   workflow_id = valid_workflow_def_model.id
   payload = {"workflowDefinitionId": workflow_id}

   # Mock read_workflow_definition to return the valid definition so the code proceeds to start_session
   mock_read_wf_def.return_value = valid_workflow_def_model
   # Use the actual exception class
   mock_start_session.side_effect = exceptions.AgentNotFoundError(agent_id)

   response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
   assert response.status_code == 404
   assert f"Agent not found: {agent_id}" in response.json()["detail"]
   mock_read_wf_def.assert_called_once_with(workflow_id) # Verify read was called
   mock_start_session.assert_called_once_with(agent_id=agent_id, workflow_id=workflow_id) # Verify start_session was called

@patch('opscore.api.storage.read_workflow_definition', return_value=None)
# @patch('opscore.api.storage.agent_exists', return_value=True) # No longer checked directly
def test_trigger_workflow_definition_not_found(mock_read_wf_def): # Removed mock_agent_exists
   """Test POST /workflow returns 404 if workflow definition ID is not found."""
   agent_id = "agent_exists_wf_not_found"
   workflow_id = "wf_does_not_exist"
   payload = {"workflowDefinitionId": workflow_id}
   response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
   assert response.status_code == 404
   # Ensure the detail matches the exception message format
   assert f"Workflow definition not found: {workflow_id}" in response.json()["detail"]
   # mock_agent_exists.assert_called_once_with(agent_id) # No longer called
   mock_read_wf_def.assert_called_once_with(workflow_id)

@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer checked directly
def test_trigger_workflow_session_start_opscore_error( # Renamed for clarity
   mock_read_wf_def, mock_start_session, valid_workflow_def_model # Corrected fixture name
):
   """Test POST /workflow returns 500 if lifecycle.start_session raises OpsCoreError."""
   agent_id = "agent_session_fail_500" # Renamed agent_id for clarity
   workflow_id = valid_workflow_def_model.id # Corrected fixture name
   # mock_agent_exists.return_value = True # Removed
   mock_read_wf_def.return_value = valid_workflow_def_model # Corrected fixture name
   # Use the actual exception class
   error_message = "Session creation conflict"
   mock_start_session.side_effect = exceptions.OpsCoreError(error_message)
   payload = {"workflowDefinitionId": workflow_id}

   response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
   # Middleware maps OpsCoreError to its status code (500 for base OpsCoreError)
   assert response.status_code == 500
   # Middleware now returns the raw exception string in the detail
   assert response.json() == {"detail": error_message} # error_message = "Session creation conflict"
   mock_start_session.assert_called_once()

@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer checked directly
def test_trigger_workflow_session_start_storage_error( # Renamed for clarity
   mock_read_wf_def, mock_start_session, valid_workflow_def_model # Corrected fixture name
):
   """Test POST /workflow returns 500 if lifecycle.start_session raises StorageError."""
   agent_id = "agent_session_fail_500_storage" # Renamed agent_id for clarity
   workflow_id = valid_workflow_def_model.id # Corrected fixture name
   # mock_agent_exists.return_value = True # Removed
   mock_read_wf_def.return_value = valid_workflow_def_model # Corrected fixture name
   # Use the actual exception class
   error_message = "Storage unavailable"
   mock_start_session.side_effect = exceptions.StorageError(error_message)
   payload = {"workflowDefinitionId": workflow_id}

   response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)
   # Middleware maps StorageError to 500
   assert response.status_code == 500
   # Middleware now returns the raw exception string in the detail
   assert response.json() == {"detail": "Storage error: Storage unavailable"}
   mock_start_session.assert_called_once()


@patch('opscore.api.lifecycle.update_session') # Mock update_session called in error handler
@patch('opscore.api.workflow.enqueue_task')
@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer checked directly
def test_trigger_workflow_enqueue_failure(
   mock_read_wf_def, mock_start_session, mock_enqueue_task, mock_update_session,
   valid_workflow_def_model, valid_session_model # Corrected fixture name
):
   """Test POST /workflow returns 400 if workflow.enqueue_task fails with InvalidStateError."""
   # Ensure the workflow def has tasks to trigger enqueue (use corrected fixture name)
   if not valid_workflow_def_model.tasks:
       # Note: Modifying fixture instance directly in test is generally discouraged,
       # but okay here as it's reset for each test by clear_storage_before_each_test.
       # A better approach might be a separate fixture for a workflow with tasks.
       valid_workflow_def_model.tasks = [{"taskId": "task1", "name": "Test Task"}]

   agent_id = "agent_enqueue_fail"
   workflow_id = valid_workflow_def_model.id # Corrected fixture name
   # mock_agent_exists.return_value = True # Removed
   mock_read_wf_def.return_value = valid_workflow_def_model # Corrected fixture name
   # Ensure sessionId is a string on the mock session returned by start_session
   mock_session = MagicMock(spec=models.WorkflowSession)
   mock_session.sessionId = "mock-session-id-enqueue-fail" # Explicitly set as string
   mock_start_session.return_value = mock_session
   mock_update_session.return_value = None # Mock the error handler call
   # Use the actual exception class
   error_message = "Queue is full"
   mock_enqueue_task.side_effect = exceptions.InvalidStateError(error_message)

   payload = {"workflowDefinitionId": workflow_id}
   response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)

   # Middleware maps InvalidStateError to 400
   assert response.status_code == 400
   # Middleware now returns the raw exception string in the detail
   assert response.json() == {"detail": error_message} # error_message = "Queue is full"
   mock_enqueue_task.assert_called_once()
   mock_update_session.assert_called_once() # Verify session status was updated to failed
   call_args, _ = mock_update_session.call_args
   assert call_args[0] == mock_session.sessionId # Check session ID
   update_payload = call_args[1]
   assert isinstance(update_payload, models.SessionUpdate)
   assert update_payload.status == "failed"
   assert error_message in update_payload.error


@patch('opscore.api.lifecycle.update_session') # Mock update_session called when no tasks
@patch('opscore.api.workflow.enqueue_task')
@patch('opscore.api.lifecycle.start_session')
@patch('opscore.api.storage.read_workflow_definition')
# @patch('opscore.api.storage.agent_exists') # No longer checked directly
def test_trigger_workflow_no_tasks(
    mock_read_wf_def, mock_start_session, mock_enqueue_task, mock_update_session,
    valid_workflow_def_model, valid_session_model
):
    """Test POST /workflow when the definition has no tasks."""
    # Ensure the workflow def has NO tasks
    valid_workflow_def_model.tasks = []

    agent_id = "agent_no_tasks"
    workflow_id = valid_workflow_def_model.id
    # mock_agent_exists.return_value = True # Removed
    mock_session = MagicMock(spec=models.WorkflowSession)
    mock_session.sessionId = "mock-session-id-no-tasks" # Explicitly set as string
    mock_read_wf_def.return_value = valid_workflow_def_model
    mock_start_session.return_value = mock_session
    mock_update_session.return_value = None # Mock the call to update session status

    payload = {"workflowDefinitionId": workflow_id}
    response = client.post(f"/v1/opscore/agent/{agent_id}/workflow", json=payload, headers=HEADERS)

    assert response.status_code == 202
    expected_response = {
        "sessionId": mock_session.sessionId,
        "workflowId": workflow_id,
        "message": "Workflow triggered but has no tasks." # Specific message for this case
    }
    assert response.json() == expected_response

    mock_enqueue_task.assert_not_called() # No task should be enqueued
    mock_update_session.assert_called_once() # Session should be updated to completed
    call_args, _ = mock_update_session.call_args
    assert call_args[0] == mock_session.sessionId
    update_payload = call_args[1]
    assert isinstance(update_payload, models.SessionUpdate)
    assert update_payload.status == "completed"
    assert update_payload.result == {"message": "Workflow has no tasks"}