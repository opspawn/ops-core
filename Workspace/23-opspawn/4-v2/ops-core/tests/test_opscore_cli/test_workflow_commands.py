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
    # Mock the class instantiation within the workflow command module
    mock_instance = MagicMock()
    mocker.patch('opscore_cli.commands.workflow.OpsCoreClientSync', return_value=mock_instance)
    return mock_instance

# --- Tests for 'workflow trigger' ---

def test_workflow_trigger_success_no_payload(runner, mock_sync_client):
    """Test 'workflow trigger' successful execution without payload."""
    agent_id = "agent-w1"
    workflow_name = "cleanup_workflow"
    mock_response = {"workflow_instance_id": "wf-123", "status": "triggered"}
    mock_sync_client.trigger_workflow.return_value = mock_response

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name])

    assert result.exit_code == 0
    mock_sync_client.trigger_workflow.assert_called_once_with(
        agent_id=agent_id,
        workflow_name=workflow_name,
        payload=None
    )
    assert f"Successfully triggered workflow '{workflow_name}' for agent '{agent_id}'." in result.output
    assert "API Response:" in result.output
    assert json.dumps(mock_response, indent=2) in result.output

def test_workflow_trigger_success_with_payload(runner, mock_sync_client):
    """Test 'workflow trigger' successful execution with payload."""
    agent_id = "agent-w2"
    workflow_name = "process_data"
    payload_json = '{"input_file": "/data/input.csv", "priority": 1}'
    payload_dict = {"input_file": "/data/input.csv", "priority": 1}
    mock_response = {"workflow_instance_id": "wf-456", "status": "queued"}
    mock_sync_client.trigger_workflow.return_value = mock_response

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name, '--payload', payload_json])

    assert result.exit_code == 0
    mock_sync_client.trigger_workflow.assert_called_once_with(
        agent_id=agent_id,
        workflow_name=workflow_name,
        payload=payload_dict
    )
    assert f"Successfully triggered workflow '{workflow_name}' for agent '{agent_id}'." in result.output
    assert "API Response:" in result.output
    assert json.dumps(mock_response, indent=2) in result.output

def test_workflow_trigger_invalid_payload_json(runner, mock_sync_client):
    """Test 'workflow trigger' with invalid payload JSON."""
    agent_id = "agent-w3"
    workflow_name = "invalid_payload_test"
    invalid_payload_json = '{"input_file": "/data/input.csv", priority": 1}' # Missing quote

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name, '--payload', invalid_payload_json])

    assert result.exit_code == 0 # Command handles error
    assert "Error parsing --payload JSON" in result.stderr
    mock_sync_client.trigger_workflow.assert_not_called()

def test_workflow_trigger_payload_not_dict_warning(runner, mock_sync_client):
    """Test 'workflow trigger' with payload JSON that is not an object (should warn)."""
    agent_id = "agent-w4"
    workflow_name = "list_payload_test"
    list_payload_json = '[1, 2, 3]'
    list_payload = [1, 2, 3]
    mock_response = {"workflow_instance_id": "wf-789", "status": "triggered"}
    mock_sync_client.trigger_workflow.return_value = mock_response

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name, '--payload', list_payload_json])

    assert result.exit_code == 0
    # Check that the warning is printed to stderr
    assert "Warning: --payload was parsed but is not a JSON object (dictionary)." in result.stderr
    # Check that the SDK was still called with the parsed list
    mock_sync_client.trigger_workflow.assert_called_once_with(
        agent_id=agent_id,
        workflow_name=workflow_name,
        payload=list_payload
    )
    assert f"Successfully triggered workflow '{workflow_name}' for agent '{agent_id}'." in result.output

def test_workflow_trigger_api_error(runner, mock_sync_client):
    """Test 'workflow trigger' handling OpsCoreApiError."""
    agent_id = "agent-w-api-err"
    workflow_name = "api_error_test"
    mock_sync_client.trigger_workflow.side_effect = OpsCoreApiError(status_code=404, detail="Workflow definition not found")

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name])

    assert result.exit_code == 0 # Command handles error
    mock_sync_client.trigger_workflow.assert_called_once_with(agent_id=agent_id, workflow_name=workflow_name, payload=None)
    assert "Error triggering workflow via API: 404 - Workflow definition not found" in result.stderr

def test_workflow_trigger_sdk_error(runner, mock_sync_client):
    """Test 'workflow trigger' handling OpsCoreSDKError."""
    agent_id = "agent-w-sdk-err"
    workflow_name = "sdk_error_test"
    mock_sync_client.trigger_workflow.side_effect = OpsCoreSDKError("Request timed out")

    result = runner.invoke(cli, ['workflow', 'trigger', agent_id, workflow_name])

    assert result.exit_code == 0 # Command handles error
    mock_sync_client.trigger_workflow.assert_called_once_with(agent_id=agent_id, workflow_name=workflow_name, payload=None)
    assert "SDK Error triggering workflow: Request timed out" in result.stderr
