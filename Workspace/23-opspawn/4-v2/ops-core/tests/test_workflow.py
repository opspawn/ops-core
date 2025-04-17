"""
Unit tests for the opscore.workflow module.
"""

import pytest
from opscore import workflow, storage, models, lifecycle
from collections import deque
import yaml
import json

# Fixtures from conftest.py are automatically available

# --- Workflow Definition Management Tests ---

YAML_TEMPLATE = """
id: wf_yaml_test
name: YAML Workflow Test
version: '1.0'
tasks:
  - taskId: task1
    name: First YAML Task
    agentCapability: cap_A
    parameters: {p1: default_y}
    nextTaskId: task2
  - taskId: task2
    name: Second YAML Task
    agentCapability: cap_B
    nextTaskId: null
"""

JSON_TEMPLATE = """
{
  "id": "wf_json_test",
  "name": "JSON Workflow Test",
  "version": "1.0",
  "tasks": [
    {"taskId": "task_j1", "name": "First JSON Task", "agentCapability": "cap_C", "nextTaskId": null}
  ]
}
"""

INVALID_YAML = """
id: wf_invalid
name: Invalid Structure
tasks:
  - task1: { name: Task 1 } # Incorrect task structure
"""

def test_load_workflow_template_yaml_success():
    """Test loading a valid YAML template."""
    definition = workflow.load_workflow_template(YAML_TEMPLATE, format='yaml')
    assert isinstance(definition, dict)
    assert definition['id'] == 'wf_yaml_test'
    assert definition['name'] == 'YAML Workflow Test'
    assert len(definition['tasks']) == 2
    assert definition['tasks'][0]['taskId'] == 'task1'

def test_load_workflow_template_json_success():
    """Test loading a valid JSON template."""
    definition = workflow.load_workflow_template(JSON_TEMPLATE, format='json')
    assert isinstance(definition, dict)
    assert definition['id'] == 'wf_json_test'
    assert len(definition['tasks']) == 1

def test_load_workflow_template_invalid_format():
    """Test loading with an unsupported format raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported template format: xml"):
        workflow.load_workflow_template("<xml></xml>", format='xml')

def test_load_workflow_template_invalid_yaml_syntax():
    """Test loading YAML with invalid syntax raises ValueError."""
    # Example of truly invalid YAML syntax (e.g., unclosed bracket or bad flow)
    invalid_yaml_syntax = "key: [value1, value2"
    with pytest.raises(ValueError, match="Failed to parse workflow template"):
        workflow.load_workflow_template(invalid_yaml_syntax, format='yaml')

def test_load_workflow_template_invalid_json_content():
    """Test loading invalid JSON content raises ValueError."""
    with pytest.raises(ValueError, match="Failed to parse workflow template"):
        workflow.load_workflow_template('{"id": "test", "tasks": [}', format='json')

def test_create_workflow_success(valid_workflow_def_dict):
    """Test creating a workflow definition."""
    workflow_id = workflow.create_workflow(valid_workflow_def_dict)
    assert workflow_id == valid_workflow_def_dict['id']

    # Verify saved in storage
    retrieved_def = storage.read_workflow_definition(workflow_id)
    assert retrieved_def is not None
    assert retrieved_def.id == workflow_id
    assert retrieved_def.name == valid_workflow_def_dict['name']

def test_create_workflow_generate_id():
    """Test creating a workflow generates an ID if not provided."""
    definition_no_id = {
        "name": "Generate ID Test",
        "tasks": [{"taskId": "t1"}]
    }
    workflow_id = workflow.create_workflow(definition_no_id)
    assert workflow_id.startswith("wf_Generate_ID_Test")

    retrieved_def = storage.read_workflow_definition(workflow_id)
    assert retrieved_def is not None
    assert retrieved_def.id == workflow_id
    assert retrieved_def.name == "Generate ID Test"

def test_get_workflow_definition_success(valid_workflow_def_model):
    """Test retrieving an existing workflow definition."""
    storage.save_workflow_definition(valid_workflow_def_model) # Save first
    workflow_id = valid_workflow_def_model.id

    # workflow.get_workflow_definition now calls storage.read_workflow_definition,
    # which returns the model instance.
    retrieved_def = workflow.get_workflow_definition(workflow_id)
    assert retrieved_def is not None
    assert isinstance(retrieved_def, models.WorkflowDefinition) # Check type
    assert retrieved_def.id == workflow_id # Use dot notation
    assert retrieved_def.name == valid_workflow_def_model.name # Use dot notation
    # Compare models directly or via dump
    assert retrieved_def == valid_workflow_def_model


def test_get_workflow_definition_not_found():
    """Test retrieving a non-existent workflow definition."""
    retrieved_def = workflow.get_workflow_definition("wf_does_not_exist")
    assert retrieved_def is None

# --- Task Queue Management Tests ---

# Access the internal queue for testing (usually discouraged, but necessary for in-memory deque)
# Be aware this might change if the queue implementation changes.
def _get_queue_size():
    return len(workflow._task_queue)

def test_enqueue_task_success(valid_task_data_dict):
    """Test enqueuing a valid task."""
    initial_size = _get_queue_size()
    workflow.enqueue_task(valid_task_data_dict)
    assert _get_queue_size() == initial_size + 1
    # Check the actual item added (it's the last one)
    enqueued_task = workflow._task_queue[-1]
    assert enqueued_task['taskId'] == valid_task_data_dict['taskId']
    assert enqueued_task['workflowId'] == valid_task_data_dict['workflowId']

def test_enqueue_task_invalid_data():
    """Test enqueuing invalid task data raises ValueError."""
    invalid_task_data = {
        "workflowId": "wf_test",
        # Missing required fields like taskId, sessionId, agentId, taskDefinitionId
    }
    with pytest.raises(ValueError, match="Invalid task data"):
        workflow.enqueue_task(invalid_task_data)

def test_dequeue_task_success(valid_task_data_dict):
    """Test dequeuing a task from a non-empty queue."""
    workflow.enqueue_task(valid_task_data_dict)
    initial_size = _get_queue_size()

    dequeued_task = workflow.dequeue_task()
    assert _get_queue_size() == initial_size - 1
    assert dequeued_task is not None
    assert dequeued_task['taskId'] == valid_task_data_dict['taskId']

def test_dequeue_task_empty():
    """Test dequeuing from an empty queue returns None."""
    assert _get_queue_size() == 0 # Ensure queue is empty (thanks to autouse fixture)
    dequeued_task = workflow.dequeue_task()
    assert dequeued_task is None

# --- Error Handling Placeholder Tests (using mocker) ---

def test_handle_task_failure_triggers_retry(mocker, valid_task_data_dict):
    """Test that handle_task_failure calls retry_task if retries remain."""
    mock_retry = mocker.patch('opscore.workflow.retry_task')
    mock_fallback = mocker.patch('opscore.workflow.fallback_task')

    task_data = valid_task_data_dict.copy()
    task_data['retryCount'] = 1
    task_data['maxRetries'] = 3

    workflow.handle_task_failure(task_data, "Test error")

    mock_retry.assert_called_once_with(task_data, 2) # Called with incremented count
    mock_fallback.assert_not_called()

def test_handle_task_failure_triggers_fallback(mocker, valid_task_data_dict):
    """Test that handle_task_failure calls fallback_task if max retries exceeded."""
    mock_retry = mocker.patch('opscore.workflow.retry_task')
    mock_fallback = mocker.patch('opscore.workflow.fallback_task')

    task_data = valid_task_data_dict.copy()
    task_data['retryCount'] = 3
    task_data['maxRetries'] = 3
    error_msg = "Max retries exceeded"

    workflow.handle_task_failure(task_data, error_msg)

    mock_retry.assert_not_called()
    mock_fallback.assert_called_once_with(task_data, error_msg)

def test_retry_task_enqueues(mocker, valid_task_data_dict):
    """Test that retry_task calls enqueue_task with updated retry count."""
    mock_enqueue = mocker.patch('opscore.workflow.enqueue_task')

    task_data = valid_task_data_dict.copy()
    task_data['retryCount'] = 1
    new_retry_attempt = 2

    workflow.retry_task(task_data, new_retry_attempt)

    # Check the task data passed to enqueue_task
    mock_enqueue.assert_called_once()
    call_args, _ = mock_enqueue.call_args
    enqueued_data = call_args[0]
    assert enqueued_data['retryCount'] == new_retry_attempt
    assert enqueued_data['status'] == 'pending_retry'
    assert enqueued_data['taskId'] == task_data['taskId']

def test_fallback_task_logs_and_attempts_session_update(mocker, caplog, valid_task_data_dict):
    """Test fallback_task logs error and attempts session update (mocked)."""
    # Mock the lifecycle update function (it's commented out in the actual code)
    mock_update_session = mocker.patch('opscore.lifecycle.update_session')
    task_data = valid_task_data_dict.copy()
    final_error = "Final failure reason"

    with caplog.at_level("ERROR"): # Check ERROR level logs
        workflow.fallback_task(task_data, final_error)

    # Check logs
    assert f"Executing fallback for failed task {task_data['taskId']}" in caplog.text
    assert f"Final error: {final_error}" in caplog.text
    # The placeholder log is DEBUG, not ERROR, so we don't assert it here.
    # We assert that the main ERROR log message is present.

    # Verify update_session wasn't actually called (as it's commented out)
    mock_update_session.assert_not_called()

# --- Async Task Dispatching Tests (using mocker and pytest-asyncio) ---

@pytest.mark.asyncio
async def test_process_next_task_dequeues_and_dispatches(mocker, valid_task_data_dict):
    """Test process_next_task successfully dequeues and calls dispatch."""
    # Mock dequeue to return our task
    mock_dequeue = mocker.patch('opscore.workflow.dequeue_task', return_value=valid_task_data_dict)
    # Mock dispatch_task (async function)
    mock_dispatch = mocker.patch('opscore.workflow.dispatch_task', new_callable=mocker.AsyncMock)

    await workflow.process_next_task()

    mock_dequeue.assert_called_once()
    mock_dispatch.assert_called_once_with(valid_task_data_dict['agentId'], valid_task_data_dict) # Use assert_called_once

@pytest.mark.asyncio
async def test_process_next_task_empty_queue(mocker):
    """Test process_next_task does nothing when queue is empty."""
    mock_dequeue = mocker.patch('opscore.workflow.dequeue_task', return_value=None)
    mock_dispatch = mocker.patch('opscore.workflow.dispatch_task', new_callable=mocker.AsyncMock)

    await workflow.process_next_task()

    mock_dequeue.assert_called_once()
    mock_dispatch.assert_not_called() # Use assert_not_called

@pytest.mark.asyncio
async def test_dispatch_task_success(mocker, valid_task_data_dict):
    """Test successful task dispatch via mocked AgentKit client."""
    agent_id = valid_task_data_dict['agentId']
    # Patch where it's used (in the workflow module)
    mock_agentkit_dispatch = mocker.patch(
        'opscore.workflow.dispatch_task_to_agentkit',
        new_callable=mocker.AsyncMock,
        return_value={"status": "dispatch_ok"} # Simulate success response
    )
    mock_handle_failure = mocker.patch('opscore.workflow.handle_task_failure')

    await workflow.dispatch_task(agent_id, valid_task_data_dict)

    mock_agentkit_dispatch.assert_called_once() # Use assert_called_once for AsyncMock
    # Check payload structure passed to mock
    call_args, _ = mock_agentkit_dispatch.call_args
    assert call_args[0] == agent_id
    payload_sent = call_args[1]
    assert payload_sent['senderId'] == "opscore_system_id"
    assert payload_sent['messageType'] == "workflow_task"
    assert payload_sent['payload'] == valid_task_data_dict['payload']
    assert payload_sent['sessionContext']['taskId'] == valid_task_data_dict['taskId']

    mock_handle_failure.assert_not_called()

@pytest.mark.asyncio
async def test_dispatch_task_agentkit_connection_error(mocker, valid_task_data_dict):
    """Test dispatch failure due to AgentKit connection error triggers handler."""
    agent_id = valid_task_data_dict['agentId']
    error_message = "Connection refused"
    # Patch where it's used
    mock_agentkit_dispatch = mocker.patch(
        'opscore.workflow.dispatch_task_to_agentkit',
        new_callable=mocker.AsyncMock,
        side_effect=ConnectionError(error_message) # Simulate connection error
    )
    mock_handle_failure = mocker.patch('opscore.workflow.handle_task_failure')

    await workflow.dispatch_task(agent_id, valid_task_data_dict)

    mock_agentkit_dispatch.assert_called_once() # Use assert_called_once for AsyncMock
    mock_handle_failure.assert_called_once_with(valid_task_data_dict, f"AgentKit Connection Error: {error_message}")

@pytest.mark.asyncio
async def test_dispatch_task_other_exception(mocker, valid_task_data_dict):
    """Test dispatch failure due to other exception triggers handler."""
    agent_id = valid_task_data_dict['agentId']
    error_message = "Unexpected error during dispatch"
    # Patch where it's used
    mock_agentkit_dispatch = mocker.patch(
        'opscore.workflow.dispatch_task_to_agentkit',
        new_callable=mocker.AsyncMock,
        side_effect=Exception(error_message) # Simulate generic error
    )
    mock_handle_failure = mocker.patch('opscore.workflow.handle_task_failure')

    await workflow.dispatch_task(agent_id, valid_task_data_dict)

    mock_agentkit_dispatch.assert_called_once() # Use assert_called_once
    mock_handle_failure.assert_called_once_with(valid_task_data_dict, f"Dispatch Error: {error_message}")