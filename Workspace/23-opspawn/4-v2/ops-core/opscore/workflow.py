"""
Ops-Core Workflow Sequencing and Orchestration Subsystem

Handles parsing workflow definitions, managing task queues,
dispatching tasks to agents (via AgentKit), and error handling.
"""

import json
import yaml
import asyncio
from collections import deque
from typing import Dict, Any, Optional, List, Union

# Placeholder imports - replace with actual implementations
from . import storage, models, lifecycle # Import storage, models, and lifecycle
# from . import exceptions # TODO: Define custom exceptions later
from .logging_config import get_logger
from .agentkit_client import dispatch_task_to_agentkit # Import the placeholder client function

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

    # Validate and create the model instance
    try:
        workflow_model = models.WorkflowDefinition(**definition)
    except Exception as e: # Catch Pydantic validation errors
        logger.error(f"Invalid workflow definition structure provided: {e}", exc_info=True)
        raise ValueError(f"Invalid workflow definition structure: {e}") from e

    # Store definition using storage module
    try:
        storage.save_workflow_definition(workflow_model) # Pass the model instance
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
    definition = storage.read_workflow_definition(workflow_id) # Use read_ instead of get_
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

async def process_next_task():
    """
    Dequeues the next task and attempts to dispatch it asynchronously.
    This would typically be run by a worker process or scheduler.
    """
    logger.debug("Checking for next task to process...")
    task_data = dequeue_task()
    if task_data:
        agent_id = task_data.get('agentId')
        if not agent_id:
            logger.error(f"Dequeued task data missing 'agentId': {task_data}")
            # TODO: Handle error (e.g., move to dead-letter queue)
            return

        # Check agent state/availability via lifecycle module before dispatching
        try:
            # Use asyncio.to_thread to call the sync function from async context
            current_state = await asyncio.to_thread(lifecycle.get_state, agent_id)
        except Exception as e:
            logger.error(f"Error retrieving state for agent {agent_id}: {e}", exc_info=True)
            # Fail the task if state retrieval fails
            handle_task_failure(task_data, f"Failed to retrieve agent state: {e}")
            return # Stop processing this task

        if current_state:
            if current_state.state == 'idle':
                logger.debug(f"Agent {agent_id} is idle. Proceeding with dispatch.")
                try:
                    await dispatch_task(agent_id, task_data)
                except Exception as e:
                    # Error handling is mostly within dispatch_task, but log context here
                    logger.error(f"Error occurred during dispatch process for task {task_data.get('taskId', 'Unknown')} for agent {agent_id}: {e}", exc_info=False)
                    # Failure handling is triggered within dispatch_task if needed
            else:
                # Agent is not idle (active, error, initializing, finished, etc.)
                logger.warning(f"Agent {agent_id} is not idle (state: {current_state.state}). Re-enqueuing task {task_data.get('taskId', 'Unknown')}.")
                # TODO: Implement re-enqueue logic with potential delay/backoff later
                enqueue_task(task_data) # Re-add to the end of the queue for now
        else:
            # State not found for agent (agent unknown or never reported state)
            logger.error(f"Could not determine state for agent {agent_id}. Failing task {task_data.get('taskId', 'Unknown')}.")
            handle_task_failure(task_data, f"Agent state not found for agent {agent_id}")
    else:
        logger.debug("No tasks in queue to process.")


async def dispatch_task(agent_id: str, task_data: Dict[str, Any]):
    """
    Asynchronously dispatches a task to the specified agent via AgentKit.

    Args:
        agent_id: The ID of the target agent.
        task_data: The task details to send to the agent.
    """
    task_identifier = task_data.get('taskId', 'Unknown Task') # Use taskId from model
    logger.info(f"Dispatching task '{task_identifier}' to agent {agent_id}")

    # Construct payload for AgentKit's /run endpoint
    agentkit_payload = {
        "senderId": "opscore_system_id",
        "messageType": "workflow_task",
        "payload": task_data.get("payload", {}),
        "sessionContext": {
            "workflowId": task_data.get("workflowId"), # Match model field name
            "sessionId": task_data.get("sessionId"),   # Match model field name
            "taskId": task_identifier
        }
    }

    try:
        # Call the (placeholder) AgentKit client function
        response = await dispatch_task_to_agentkit(agent_id, agentkit_payload)
        logger.info(f"Task '{task_identifier}' dispatch acknowledged by AgentKit for agent {agent_id}. Response: {response}")
        # TODO: Update task status in storage (e.g., "dispatched") based on response
        # task_data['status'] = 'dispatched'
        # update_task_in_storage(task_data) # Requires task persistence logic
    except ConnectionError as e: # Catch specific errors raised by the client placeholder
         logger.error(f"Connection error dispatching task '{task_identifier}' to agent {agent_id} via AgentKit: {e}", exc_info=True)
         handle_task_failure(task_data, f"AgentKit Connection Error: {e}")
    except Exception as e: # Catch other potential exceptions from client/network
        logger.error(f"Failed to dispatch task '{task_identifier}' to agent {agent_id} via AgentKit: {e}", exc_info=True)
        handle_task_failure(task_data, f"Dispatch Error: {e}")


# --- Error Handling & Retry ---

def handle_task_failure(task_data: Dict[str, Any], error_message: str):
    """Handles a failed task, potentially triggering retry or fallback."""
    task_id = task_data.get('taskId', 'Unknown Task')
    agent_id = task_data.get('agentId', 'Unknown Agent')
    logger.warning(f"Handling failure for task {task_id} (agent {agent_id}): {error_message}")
    # TODO: Implement retry logic based on task definition or system policy
    retry_count = task_data.get('retryCount', 0) # Match model field name
    max_retries = task_data.get('maxRetries', 3) # Match model field name

    if retry_count < max_retries:
        logger.info(f"Attempting retry {retry_count + 1}/{max_retries} for task {task_id}")
        retry_task(task_data, retry_count + 1)
    else:
        logger.error(f"Task {task_id} failed after maximum {max_retries} retries.")
        fallback_task(task_data, error_message) # Pass error message to fallback

def retry_task(task_data: Dict[str, Any], retry_attempt: int):
    """Re-enqueues a task for a retry attempt."""
    task_id = task_data.get('taskId', 'Unknown Task')
    logger.info(f"Retrying task {task_id} (attempt {retry_attempt})")
    task_data['retryCount'] = retry_attempt # Update retry count
    task_data['status'] = 'pending_retry' # Optionally update status
    # TODO: Implement delay before re-enqueuing (e.g., exponential backoff)
    enqueue_task(task_data)


def fallback_task(task_data: Dict[str, Any], final_error: str):
    """Handles a task that has ultimately failed after retries."""
    task_id = task_data.get('taskId', 'Unknown Task')
    session_id = task_data.get('sessionId')
    agent_id = task_data.get('agentId') # Match model field name
    logger.error(f"Executing fallback for failed task {task_id} (session: {session_id}, agent: {agent_id}). Final error: {final_error}")

    # TODO: Implement more robust fallback logic:
    # 1. Mark task as 'failed' in storage (if tasks are persisted individually)
    # 2. Update the overall session status to 'failed' or 'partially_failed'
    # 3. Notify monitoring system / Log detailed error context
    # 4. Trigger a compensating action or alternative workflow if defined

    if session_id:
        logger.info(f"Attempting to mark session {session_id} as failed due to task {task_id} failure.")
        try:
            update_payload = models.SessionUpdate(
                status="failed",
                error=f"Task {task_id} failed after max retries: {final_error}"
                # Optionally add more context to metadata if needed
            )
            # lifecycle.update_session(session_id, update_payload) # Keep commented until fully integrated and tested
            logger.debug(f"Placeholder: Would call lifecycle.update_session for {session_id} with status 'failed'.")
        except Exception as e:
            logger.error(f"Failed to update session {session_id} status during fallback for task {task_id}: {e}", exc_info=True)
    else:
        logger.warning(f"Cannot update session status for failed task {task_id} as session_id is missing.")

# --- Utility Functions ---

# def schedule_task(task_data: Dict[str, Any], delay_seconds: int):
#     """Schedules a task to be enqueued after a delay."""
#     # logger.info(f"Scheduling task {task_data.get('task_name', 'N/A')} with delay {delay_seconds}s")
#     # TODO: Implement scheduling mechanism (e.g., using APScheduler, Celery eta)
# print(f"Placeholder: Scheduled task {task_data.get('task_name', 'N/A')} with delay {delay_seconds}s")