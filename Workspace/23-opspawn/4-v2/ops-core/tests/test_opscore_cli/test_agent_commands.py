import pytest
import json
from click.testing import CliRunner
from opscore_cli.main import cli
from opscore_sdk.exceptions import OpsCoreApiError, OpsCoreSDKError
from unittest.mock import MagicMock

# Fixture for the CliRunner
@pytest.fixture
def runner():
    # Initialize with mix_stderr=False to allow checking result.stderr
    return CliRunner(mix_stderr=False)

# Fixture to mock the OpsCoreClientSync instance used by the commands
@pytest.fixture
def mock_sync_client(mocker):
    # Mock the class instantiation within the agent command module
    mock_instance = MagicMock()
    mocker.patch('opscore_cli.commands.agent.OpsCoreClientSync', return_value=mock_instance)
    return mock_instance

# --- Tests for 'agent get-state' ---

def test_agent_get_state_success(runner, mock_sync_client):
    """Test 'agent get-state' successful execution."""
    agent_id = "agent-abc"
    mock_state = {"agent_id": agent_id, "state": "idle", "details": {"foo": "bar"}, "last_updated": "2024-01-01T10:00:00Z"}
    mock_sync_client.get_agent_state.return_value = mock_state

    result = runner.invoke(cli, ['agent', 'get-state', agent_id])

    assert result.exit_code == 0
    mock_sync_client.get_agent_state.assert_called_once_with(agent_id=agent_id)
    # Check if the output is the JSON representation of the mock state
    expected_output = json.dumps(mock_state, indent=2)
    assert expected_output in result.output

def test_agent_get_state_api_error(runner, mock_sync_client):
    """Test 'agent get-state' handling OpsCoreApiError."""
    agent_id = "agent-xyz"
    mock_sync_client.get_agent_state.side_effect = OpsCoreApiError(status_code=404, detail="Agent not found")

    result = runner.invoke(cli, ['agent', 'get-state', agent_id])

    assert result.exit_code == 0 # Command should handle error gracefully
    mock_sync_client.get_agent_state.assert_called_once_with(agent_id=agent_id)
    assert "Error getting agent state from API: 404 - Agent not found" in result.stderr

def test_agent_get_state_sdk_error(runner, mock_sync_client):
    """Test 'agent get-state' handling OpsCoreSDKError."""
    agent_id = "agent-sdk-err"
    mock_sync_client.get_agent_state.side_effect = OpsCoreSDKError("Connection failed")

    result = runner.invoke(cli, ['agent', 'get-state', agent_id])

    assert result.exit_code == 0 # Command should handle error gracefully
    mock_sync_client.get_agent_state.assert_called_once_with(agent_id=agent_id)
    assert "SDK Error getting agent state: Connection failed" in result.stderr

# --- Tests for 'agent update-state' ---

def test_agent_update_state_success_no_details(runner, mock_sync_client):
    """Test 'agent update-state' successful execution without details."""
    agent_id = "agent-123"
    new_state = "active"

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state])

    assert result.exit_code == 0
    mock_sync_client.update_agent_state.assert_called_once_with(agent_id=agent_id, state=new_state, details=None)
    assert f"Successfully requested state update for agent '{agent_id}' to '{new_state}'" in result.output

def test_agent_update_state_success_with_details(runner, mock_sync_client):
    """Test 'agent update-state' successful execution with details."""
    agent_id = "agent-456"
    new_state = "error"
    details_json = '{"code": 500, "message": "Internal Server Error"}'
    details_dict = {"code": 500, "message": "Internal Server Error"}

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state, '--details', details_json])

    assert result.exit_code == 0
    mock_sync_client.update_agent_state.assert_called_once_with(agent_id=agent_id, state=new_state, details=details_dict)
    assert f"Successfully requested state update for agent '{agent_id}' to '{new_state}'" in result.output

def test_agent_update_state_invalid_details_json(runner, mock_sync_client):
    """Test 'agent update-state' with invalid details JSON."""
    agent_id = "agent-789"
    new_state = "idle"
    invalid_details_json = '{"code": 500, message": "Missing quote}' # Invalid JSON

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state, '--details', invalid_details_json])

    assert result.exit_code == 0 # Command handles error, doesn't crash
    assert "Error parsing --details JSON" in result.stderr
    mock_sync_client.update_agent_state.assert_not_called() # Should not call SDK

def test_agent_update_state_details_not_dict(runner, mock_sync_client):
    """Test 'agent update-state' with details JSON that is not an object."""
    agent_id = "agent-abc"
    new_state = "idle"
    not_dict_json = '[1, 2, 3]' # Valid JSON, but not a dictionary

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state, '--details', not_dict_json])

    assert result.exit_code == 0 # Command handles error
    assert "Error: --details must be a valid JSON object (dictionary)." in result.stderr
    mock_sync_client.update_agent_state.assert_not_called()

def test_agent_update_state_invalid_state_choice(runner, mock_sync_client):
    """Test 'agent update-state' with an arbitrary state string (validation removed from click)."""
    agent_id = "agent-def"
    invalid_state = "pending"

    # Since click.Choice was removed, click no longer validates the state.
    # The command should now execute successfully (exit code 0) and pass
    # the arbitrary state string to the SDK client.
    result = runner.invoke(cli, ['agent', 'update-state', agent_id, invalid_state])

    assert result.exit_code == 0
    # Verify the mock client was called with the arbitrary state string
    mock_sync_client.update_agent_state.assert_called_once_with(
        agent_id=agent_id, state=invalid_state, details=None
    )
    assert f"Successfully requested state update for agent '{agent_id}' to '{invalid_state}'" in result.output

def test_agent_update_state_api_error(runner, mock_sync_client):
    """Test 'agent update-state' handling OpsCoreApiError."""
    agent_id = "agent-api-err"
    new_state = "active"
    mock_sync_client.update_agent_state.side_effect = OpsCoreApiError(status_code=400, detail="Invalid state transition")

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state])

    assert result.exit_code == 0 # Command handles error
    mock_sync_client.update_agent_state.assert_called_once_with(agent_id=agent_id, state=new_state, details=None)
    assert "Error updating agent state via API: 400 - Invalid state transition" in result.stderr

def test_agent_update_state_sdk_error(runner, mock_sync_client):
    """Test 'agent update-state' handling OpsCoreSDKError."""
    agent_id = "agent-sdk-err"
    new_state = "idle"
    mock_sync_client.update_agent_state.side_effect = OpsCoreSDKError("Network timeout")

    result = runner.invoke(cli, ['agent', 'update-state', agent_id, new_state])

    assert result.exit_code == 0 # Command handles error
    mock_sync_client.update_agent_state.assert_called_once_with(agent_id=agent_id, state=new_state, details=None)
    assert "SDK Error updating agent state: Network timeout" in result.stderr