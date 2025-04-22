"""
Ops-Core Lifecycle Management Subsystem

Handles agent registration, state tracking, and session management.
"""

import uuid # Import uuid module
from datetime import datetime, timezone # Import timezone
from typing import Dict, Any, Optional, List

# Placeholder imports - replace with actual implementations
from .storage import get_storage # Import get_storage instead of the whole module
from . import exceptions # Import custom exceptions
from .models import AgentInfo, AgentRegistrationDetails, AgentState, WorkflowSession, SessionUpdate
from .logging_config import get_logger

logger = get_logger(__name__)

# --- Agent Registration ---

async def register_agent(agent_id: str, details: AgentRegistrationDetails) -> AgentInfo:
    """ # Corrected indentation (4 spaces)
    Registers a new agent with Ops-Core using the provided agent ID. (Async) # Corrected indentation (4 spaces)

    Args: # Corrected indentation (4 spaces)
        agent_id: The unique ID for the agent (provided by AgentKit). # Corrected indentation (8 spaces)
        details: Pydantic model containing agent metadata (name, version, etc.). # Corrected indentation (8 spaces)

    Returns: # Corrected indentation (4 spaces)
        The AgentInfo object representing the registered agent. # Corrected indentation (8 spaces)

    Raises: # Corrected indentation (4 spaces)
        pydantic.ValidationError: If agent_details are invalid. # Corrected indentation (8 spaces)
        exceptions.RegistrationError: If storage fails during registration. # Corrected indentation (8 spaces)
    """ # Corrected indentation (4 spaces)
    logger.debug("Lifecycle: Entering register_agent function.")
    agent_name = details.agentName # Corrected indentation (4 spaces)
    logger.info(f"Lifecycle: Attempting to register agent: {agent_name} with ID: {agent_id}")

    # Validate agent_id format? (Optional, assume valid string for now)
    if not agent_id:
        raise ValueError("agent_id cannot be empty")

    # Create the full AgentInfo object using provided ID and details
    try:
        agent_info = AgentInfo(
            **details.model_dump(), # Spread the details (includes agentId)
            registrationTime=datetime.now(timezone.utc) # Set registration time to now
        )
        logger.debug(f"Lifecycle: Created AgentInfo model for agent {agent_id}")
    except Exception as e: # Catch potential Pydantic validation errors
        logger.error(f"Lifecycle: Failed to create AgentInfo model for agent {agent_id}: {e}", exc_info=True)
        # Use a more specific exception if available, or re-raise validation error
        raise exceptions.RegistrationError(f"Invalid agent details provided for {agent_id}", original_exception=e) from e

    # Store agent registration data using the storage module
    logger.debug(f"Lifecycle: Calling storage.save_agent_registration for agent {agent_id}")
    storage_instance = get_storage()
    logger.debug(f"Lifecycle: Calling storage.save_agent_registration for agent {agent_id}")
    try:
        await storage_instance.save_agent_registration(agent_info)
        logger.info(f"Lifecycle: Agent '{agent_name}' registration data saved successfully with ID: {agent_id}")

        # Set initial state after successful registration storage
        logger.debug(f"Lifecycle: Calling set_state for initial UNKNOWN state for agent {agent_id}")
        try:
            # Call the async set_state function
            await set_state(agent_id=agent_id, new_state="UNKNOWN", details={"reason": "Initial registration"})
            logger.info(f"Lifecycle: Initial state 'UNKNOWN' set for agent {agent_id}")
        except Exception as state_e:
            # Log error setting initial state, but don't fail the registration itself?
            # Or should we attempt to rollback/delete the registration?
            # For now, log error and continue. Consider cleanup later.
            logger.error(f"Lifecycle: Failed to set initial state for newly registered agent {agent_id}: {state_e}", exc_info=True)
            # Optionally raise a specific warning/error or just proceed

    except exceptions.AgentAlreadyExistsError as e: # Catch specific error from storage
        logger.warning(f"Lifecycle: Attempted to register agent {agent_id} which already exists.")
        raise e # Re-raise for the API layer to handle
    except Exception as e:
        logger.error(f"Lifecycle: Failed to save registration for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.RegistrationError(f"Failed to save registration for agent {agent_id}", original_exception=e) from e

    logger.debug("Lifecycle: Exiting register_agent function.")
    return agent_info

# --- State Management ---

async def set_state(agent_id: str, new_state: str, details: Optional[Dict[str, Any]] = None, timestamp: Optional[str] = None):
    """
    Updates the state of a registered agent. (Async)

    Args:
        agent_id: The ID of the agent to update.
        new_state: The new state string (e.g., "idle", "active", "error").
        details: Optional dictionary containing context about the state change.
        timestamp: Optional ISO 8601 timestamp string of when the state occurred.

    Raises:
        exceptions.AgentNotFoundError: If the agent_id is not found.
        exceptions.InvalidStateError: If the new_state data is invalid (e.g., Pydantic validation).
        exceptions.StorageError: If saving the state to storage fails.
    """
    logger.info(f"Lifecycle: Setting state for agent {agent_id} to '{new_state}'")
    storage_instance = get_storage()
    # Validate agent_id exists using storage module (read operation)
    logger.debug(f"Lifecycle: Checking if agent {agent_id} exists before setting state.")
    if not await storage_instance.read_agent_registration(agent_id):
        logger.error(f"Lifecycle: Attempted to set state for unknown agent ID: {agent_id}")
        raise exceptions.AgentNotFoundError(agent_id)
    logger.debug(f"Lifecycle: Agent {agent_id} found.")

    # TODO: Validate new_state against allowed states (defined in models?)

    # TODO: Parse timestamp string to datetime object if provided
    state_timestamp = datetime.now(timezone.utc) # Default to now (timezone-aware)
    if timestamp:
        try:
            # Attempt to parse timestamp, fallback to now if invalid
            # Ensure timezone awareness if needed, Pydantic might handle this better
            state_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Lifecycle: Invalid timestamp format received for agent {agent_id}: '{timestamp}'. Using current time.")
            # Keep state_timestamp as datetime.utcnow()

    # Create state update object using the Pydantic model
    try:
        agent_state = AgentState(
            agentId=agent_id,
            state=new_state,
            details=details,
            timestamp=state_timestamp
        )
        logger.debug(f"Lifecycle: Created AgentState model for agent {agent_id}")
    except Exception as e: # Catch potential Pydantic validation errors
        logger.error(f"Lifecycle: Failed to create AgentState model for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.InvalidStateError(f"Invalid state data provided: {e}") from e

    # Store the state update using the storage module
    logger.debug(f"Lifecycle: Calling storage.save_agent_state for agent {agent_id}")
    storage_instance = get_storage()
    logger.debug(f"Lifecycle: Calling storage.save_agent_state for agent {agent_id}")
    try:
        await storage_instance.save_agent_state(agent_state)
        logger.info(f"Lifecycle: State for agent {agent_id} updated to '{new_state}'")
    except Exception as e:
        logger.error(f"Lifecycle: Failed to save state for agent {agent_id} to storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id}", original_exception=e) from e


async def get_state(agent_id: str) -> Optional[AgentState]:
    """
    Retrieves the current state of a registered agent. (Async)

    Args:
        agent_id: The ID of the agent.

    Returns:
        An AgentState object representing the agent's current state,
        or None if the agent or state is not found.
    """
    logger.debug(f"Lifecycle: Fetching state for agent {agent_id}")
    storage_instance = get_storage()
    # Retrieve state from storage module
    logger.debug(f"Lifecycle: Calling storage.read_latest_agent_state for agent {agent_id}")
    agent_state = await storage_instance.read_latest_agent_state(agent_id)
    logger.debug(f"Lifecycle: storage.read_latest_agent_state returned: {agent_state}")
    if agent_state:
        logger.debug(f"Lifecycle: Found state for agent {agent_id}: {agent_state.state}")
        return agent_state
    else:
        logger.warning(f"Lifecycle: No state found for agent {agent_id}")
        return None

# --- Session Management ---

async def start_session(agent_id: str, workflow_id: str) -> WorkflowSession:
    """
    Starts a new workflow session for an agent. (Async)

    Args:
        agent_id: The ID of the agent involved in the session.
        workflow_id: The ID of the workflow being executed.

    Returns:
        The created WorkflowSession object.

    Raises:
        exceptions.AgentNotFoundError: If the agent_id is not found.
        exceptions.OpsCoreError: If the session object cannot be initialized.
        exceptions.StorageError: If saving the session to storage fails.
    """
    logger.info(f"Lifecycle: Attempting to start new session for agent {agent_id}, workflow {workflow_id}")

    storage_instance = get_storage()
    # Validate agent_id exists
    logger.debug(f"Lifecycle: Checking if agent {agent_id} exists before starting session.")
    if not await storage_instance.read_agent_registration(agent_id):
        logger.error(f"Lifecycle: Cannot start session: Agent {agent_id} not found.")
        raise exceptions.AgentNotFoundError(agent_id)
    logger.debug(f"Lifecycle: Agent {agent_id} found.")

    # Create session object (generates its own ID and timestamps)
    try:
        session = WorkflowSession(
            agentId=agent_id,
            workflowId=workflow_id,
            # sessionId, startTime, last_updated_time, status are handled by model defaults
        )
        logger.debug(f"Lifecycle: Created WorkflowSession model for agent {agent_id}, workflow {workflow_id}")
    except Exception as e: # Should not happen with these args, but good practice
        logger.error(f"Lifecycle: Failed to create WorkflowSession model: {e}", exc_info=True)
        raise exceptions.OpsCoreError(f"Failed to initialize session object: {e}") from e

    storage_instance = get_storage()
    # Store session data using storage module
    logger.debug(f"Lifecycle: Calling storage.create_session for session {session.sessionId}")
    try:
        await storage_instance.create_session(session)
        logger.info(f"Lifecycle: Session {session.sessionId} started successfully for agent {agent_id}, workflow {workflow_id}")
    except ValueError as e: # Catch potential duplicate ID error from storage
        logger.error(f"Lifecycle: Failed to create session in storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to create session: {e}", original_exception=e) from e
    except Exception as e:
        logger.error(f"Lifecycle: Failed to save session {session.sessionId} to storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save session {session.sessionId}", original_exception=e) from e

    return session

async def update_session(session_id: str, update_payload: SessionUpdate) -> WorkflowSession:
    """
    Updates an existing workflow session using provided data. (Async)

    Args:
        session_id: The ID of the session to update.
        update_payload: A SessionUpdate Pydantic model containing the fields to update.

    Returns:
        The updated WorkflowSession object.

    Raises:
        exceptions.SessionNotFoundError: If the session_id is not found.
        exceptions.InvalidStateError: If the update data is invalid.
        exceptions.StorageError: If updating the session in storage fails.
    """
    logger.info(f"Lifecycle: Attempting to update session {session_id}")

    # Prepare update dictionary, only including fields explicitly set in the payload
    update_dict = update_payload.model_dump(exclude_unset=True)

    if not update_dict:
        logger.warning(f"Lifecycle: Update called for session {session_id} with no changes provided.")
        storage_instance = get_storage()
        # Optionally return the existing session without hitting storage
        existing_session = await storage_instance.read_session(session_id)
        if not existing_session:
             raise exceptions.SessionNotFoundError(session_id)
        return existing_session


    # Always update the last_updated_time
    update_dict['last_updated_time'] = datetime.now(timezone.utc) # Use timezone-aware

    # If status is changing to a terminal state, set endTime if not already set
    if 'status' in update_dict and update_dict['status'] in ['completed', 'failed', 'cancelled']:
        if 'endTime' not in update_dict: # Only set if not explicitly provided
            update_dict['endTime'] = datetime.now(timezone.utc) # Use timezone-aware

    logger.debug(f"Lifecycle: Applying updates to session {session_id}: {update_dict}")

    storage_instance = get_storage()
    logger.debug(f"Lifecycle: Calling storage.update_session_data for session {session_id}")
    try:
        updated_session = await storage_instance.update_session_data(session_id, update_dict)
        logger.info(f"Lifecycle: Session {session_id} updated successfully.")
        return updated_session
    except exceptions.SessionNotFoundError as e: # Catch specific not found error from storage
        logger.error(f"Lifecycle: Update failed: Session {session_id} not found.")
        raise e # Re-raise the specific SessionNotFoundError
    except exceptions.InvalidStateError as e: # Catch specific invalid data error from storage
        logger.error(f"Lifecycle: Update failed for session {session_id} due to invalid data: {e}", exc_info=True)
        raise e # Re-raise the specific InvalidStateError
    except Exception as e: # Catch other potential storage or unexpected errors
        logger.error(f"Lifecycle: Failed to update session {session_id} in storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to update session {session_id}", original_exception=e) from e


async def get_session(session_id: str) -> Optional[WorkflowSession]:
    """
    Retrieves details of a specific workflow session. (Async)

    Args:
        session_id: The ID of the session.

    Returns:
        A WorkflowSession object representing the session data, or None if not found.
    """
    logger.debug(f"Lifecycle: Fetching session details for {session_id}")
    storage_instance = get_storage()
    logger.debug(f"Lifecycle: Calling storage.read_session for session {session_id}")
    session = await storage_instance.read_session(session_id)
    logger.debug(f"Lifecycle: storage.read_session returned: {session}")
    if session:
        logger.debug(f"Lifecycle: Found session {session_id}")
    else:
        logger.warning(f"Lifecycle: No session found for ID: {session_id}")
    return session