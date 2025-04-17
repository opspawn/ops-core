"""
Ops-Core Workflow Sequencing and Orchestration Subsystem

Handles parsing workflow definitions, managing task queues,
dispatching tasks to agents (via AgentKit), and error handling.
"""

import json
import yaml
from collections import deque
from typing import Dict, Any, Optional, List, Union

# Placeholder imports - replace with actual implementations
from . import storage, models # Import storage and models
# from . import exceptions, lifecycle # TODO: Define custom exceptions later
from .logging_config import get_logger
# from .agentkit_client import dispatch_task_to_agentkit # Assumes an AgentKit client module

logger = get_logger(__name__)

# In-memory queue for tasks (replace with persistent queue later)
_task_queue: deque = deque()

# In-memory storage for workflow definitions is now handled by the storage module
# _workflow_definitions: Dict[str, Dict[str, Any]] = {}

# --- Workflow Definition Management ---

def load_workflow_template(template_content: str, format: str = 'yaml') -> Dict[str, Any]:
    """
    Parses a workflow template string (JSON or YAML).

    Args:
        template_content: The string content of the workflow template.
        format: The format of the template ('json' or 'yaml').

    Returns:
        A dictionary representing the parsed workflow definition.

    Raises:
        ValueError: If the format is invalid or parsing fails.
    """
    logger.info(f"Loading workflow template (format: {format})")
    try:
        if format == 'yaml':
            definition = yaml.safe_load(template_content)
        elif format == 'json':
            definition = json.loads(template_content)
        else:
            raise ValueError(f"Unsupported template format: {format}")
        # TODO: Validate definition against a schema (models.WorkflowDefinition)
        if not isinstance(definition, dict):
             # Handle cases where YAML/JSON parsing results in non-dict types (e.g., just a string)
             raise ValueError("Parsed template content is not a valid dictionary structure.")
        logger.info(f"Workflow template loaded successfully: {definition.get('name', 'N/A')}")
        return definition
    except (yaml.YAMLError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to load workflow template: {e}", exc_info=True)
        raise ValueError(f"Failed to parse workflow template: {e}") from e

def create_workflow(definition: Dict[str, Any]) -> str:
    """
    Stores a parsed workflow definition.

    Args:
        definition: The parsed workflow definition dictionary.

    Returns:
        The ID assigned to the workflow definition.
    """
    # TODO: Validate definition structure using models.WorkflowDefinition?
    # Generate ID if not provided in definition
    workflow_id = definition.get('id')
    if not workflow_id:
        workflow_name = definition.get('name', 'unnamed').replace(' ', '_')
        # Consider adding a UUID or hash for more uniqueness if needed
        workflow_id = f"wf_{workflow_name}"
        definition['id'] = workflow_id # Add generated ID back to definition dict
        logger.debug(f"Generated workflow ID: {workflow_id}")

    logger.info(f"Creating workflow definition with ID: {workflow_id}")

    # Store definition using storage module
    try:
        storage.save_workflow_definition(workflow_id, definition)
        logger.info(f"Workflow definition '{workflow_id}' created and saved.")
    except Exception as e:
        logger.error(f"Failed to save workflow definition {workflow_id}: {e}", exc_info=True)
        # TODO: Define specific storage exception
        raise IOError(f"Failed to save workflow definition {workflow_id}")

    return workflow_id

def get_workflow_definition(workflow_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a stored workflow definition.

    Args:
        workflow_id: The ID of the workflow definition.

    Returns:
        The workflow definition dictionary, or None if not found.
    """
    logger.debug(f"Fetching workflow definition for ID: {workflow_id}")
    # Retrieve from storage module
    definition = storage.get_workflow_definition(workflow_id)
    # definition = _workflow_definitions.get(workflow_id) # In-memory placeholder REMOVED
    if definition:
        logger.debug(f"Found workflow definition {workflow_id}")
    else:
        logger.warning(f"Workflow definition not found for ID: {workflow_id}")
    return definition

# --- Task Queue Management ---

def enqueue_task(task_data: Dict[str, Any]):
    """
    Adds a task to the processing queue after validation.

    Args:
        task_data: Dictionary representing the task.

    Raises:
        ValueError: If task_data fails validation against models.Task.
    """
    logger.info(f"Attempting to enqueue task for agent {task_data.get('agentId', 'N/A')}, workflow {task_data.get('workflowId')}")

    # Validate task_data structure using the Pydantic model
    try:
        # Create a Task model instance to validate. We might not store the
        # model instance directly in the deque if we want simple dicts there.
        task_model = models.Task(**task_data)
        # Use the validated data from the model for consistency
        validated_task_data = task_model.model_dump()
    except Exception as e: # Catch Pydantic validation errors
        logger.error(f"Invalid task data provided for enqueue: {e}", exc_info=True)
        raise ValueError(f"Invalid task data: {e}")

    # TODO: Persist task to a reliable queue (e.g., Redis list, Celery) instead of just in-memory deque
    _task_queue.append(validated_task_data) # Add validated data to the queue
    logger.debug(f"Task enqueued. Queue size: {len(_task_queue)}")

def dequeue_task() -> Optional[Dict[str, Any]]:
    """
    Removes and returns the next task from the queue (FIFO).

    Returns:
        The task data dictionary, or None if the queue is empty.
    """
    if not _task_queue:
        # logger.debug("Task queue is empty.") # Already uncommented
        return None

    # TODO: Implement reliable dequeue from persistent queue
    task_data = _task_queue.popleft()
    # logger.info(f"Dequeued task: {task_data.get('task_name', 'N/A')} for agent {task_data.get('agent_id')}") # Already uncommented
    # logger.debug(f"Queue size after dequeue: {len(_task_queue)}") # Already uncommented
    return task_data

# --- Task Dispatching ---

def process_next_task():
    """
    Dequeues the next task and attempts to dispatch it.
    This would typically be run by a worker process or scheduler.
    """
    logger.debug("Checking for next task to process...")
    task_data = dequeue_task()
    if task_data:
        # Ensure agent_id is present (already validated in enqueue_task, but good practice)
        agent_id = task_data.get('agentId') # Match Pydantic model field name
        if not agent_id:
            logger.error(f"Dequeued task data missing 'agentId': {task_data}")
            # TODO: Handle error (e.g., move to dead-letter queue)
            return

        # TODO: Check agent state/availability via lifecycle module before dispatching?
        # This requires lifecycle.get_state to be fully implemented first.
        # current_state_info = lifecycle.get_state(agent_id)
        # if current_state_info and current_state_info.get('state') == 'idle':
        #     logger.debug(f"Agent {agent_id} is idle. Proceeding with dispatch.")
        #     dispatch_task(agent_id, task_data)
        # elif current_state_info:
        #     logger.warning(f"Agent {agent_id} is not idle (state: {current_state_info.get('state', 'unknown')}). Re-enqueuing task.")
        #     # TODO: Implement re-enqueue logic with potential delay
        #     enqueue_task(task_data) # Re-add to the end of the queue for now
        #     return
        # else:
        #     # Agent state unknown or agent not found, handle appropriately
        #     logger.error(f"Could not determine state for agent {agent_id}. Cannot dispatch task.")
        #     # TODO: Decide how to handle this - fail task? Re-enqueue?
        #     return

        # Simple dispatch for now (bypassing state check)
        logger.debug(f"Bypassing agent state check for now. Dispatching task for agent {agent_id}.")
        dispatch_task(agent_id, task_data)
    else:
        logger.debug("No tasks in queue to process.")


def dispatch_task(agent_id: str, task_data: Dict[str, Any]):
    """
    Dispatches a task to the specified agent via AgentKit.

    Args:
        agent_id: The ID of the target agent.
        task_data: The task details to send to the agent.
    """
    # Extract task identifier for logging, default to task_id or 'Unknown Task'
    task_identifier = task_data.get('task_name', task_data.get('taskId', 'Unknown Task'))
    logger.info(f"Dispatching task '{task_identifier}' to agent {agent_id}")

    # Construct payload for AgentKit's /run endpoint
    agentkit_payload = {
        "senderId": "opscore_system_id", # Consistent ID for Ops-Core
        "messageType": "workflow_task", # Or derive from task_data
        "payload": task_data.get("payload", {}), # The actual task parameters/content
        "sessionContext": {
            "workflowId": task_data.get("workflow_id"),
            "sessionId": task_data.get("session_id"),
            "taskId": task_data.get("task_id") # Assuming tasks have unique IDs
        }
    }

    try:
        # TODO: Call the AgentKit client function
        # response = dispatch_task_to_agentkit(agent_id, agentkit_payload)
        logger.info(f"Task dispatch acknowledged by AgentKit for agent {agent_id}. Response: {{response}}") # Placeholder response
        # Note: AgentKit's ack doesn't mean the agent processed it. State updates are separate.
        # TODO: Update task status in storage (e.g., "dispatched")
    except Exception as e: # Replace with specific client exceptions
        logger.error(f"Failed to dispatch task '{task_identifier}' to agent {agent_id} via AgentKit: {e}", exc_info=True)
        # TODO: Handle dispatch failure (e.g., retry, mark task as failed, trigger fallback)
        handle_task_failure(task_data, str(e))


# --- Error Handling & Retry ---

def handle_task_failure(task_data: Dict[str, Any], error_message: str):
    """Handles a failed task, potentially triggering retry or fallback."""
    # logger.warning(f"Handling failure for task {task_data.get('task_id')} (agent {task_data.get('agent_id')}): {error_message}") # Already uncommented
    # TODO: Implement retry logic based on task definition or system policy
    retry_count = task_data.get('retry_count', 0)
    max_retries = task_data.get('max_retries', 3) # Get from task or workflow definition

    if retry_count < max_retries:
        retry_task(task_data, retry_count + 1)
    # else: # Already uncommented
        # logger.error(f"Task {task_data.get('task_id')} failed after {max_retries} retries.") # Already uncommented
        fallback_task(task_data)

def retry_task(task_data: Dict[str, Any], retry_attempt: int):
    """Re-enqueues a task for a retry attempt."""
    # logger.info(f"Retrying task {task_data.get('task_id')} (attempt {retry_attempt})") # Already uncommented
    task_data['retry_count'] = retry_attempt
    # TODO: Implement delay before re-enqueuing?
    enqueue_task(task_data)


def fallback_task(task_data: Dict[str, Any]):
    """Handles a task that has ultimately failed after retries."""
    # logger.error(f"Executing fallback for failed task {task_data.get('task_id')}") # Already uncommented
    # TODO: Implement fallback logic:
    # - Mark task/session as failed in storage
    # - Notify monitoring system
    # - Trigger a compensating action or alternative workflow?
    session_id = task_data.get('session_id')
    agent_id = task_data.get('agent_id')
    if session_id and agent_id:
        # lifecycle.update_session(agent_id, session_id, {"status": "failed", "error": "Max retries exceeded"})
        pass

# --- Utility Functions ---

# def schedule_task(task_data: Dict[str, Any], delay_seconds: int):
#     """Schedules a task to be enqueued after a delay."""
#     # logger.info(f"Scheduling task {task_data.get('task_name', 'N/A')} with delay {delay_seconds}s")
#     # TODO: Implement scheduling mechanism (e.g., using APScheduler, Celery eta)
# print(f"Placeholder: Scheduled task {task_data.get('task_name', 'N/A')} with delay {delay_seconds}s")