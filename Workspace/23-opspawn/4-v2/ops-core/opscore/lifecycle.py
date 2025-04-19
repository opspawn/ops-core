"""
Ops-Core Lifecycle Management Subsystem

Handles agent registration, state tracking, and session management.
"""

import uuid # Import uuid module
from datetime import datetime, timezone # Import timezone
from typing import Dict, Any, Optional, List

# Placeholder imports - replace with actual implementations
from . import storage
from . import exceptions # Import custom exceptions
from .models import AgentInfo, AgentRegistrationDetails, AgentState, WorkflowSession, SessionUpdate
from .logging_config import get_logger

logger = get_logger(__name__)

# --- Agent Registration ---

def register_agent(agent_id: str, details: AgentRegistrationDetails) -> AgentInfo:
    """ # Corrected indentation (4 spaces)
    Registers a new agent with Ops-Core using the provided agent ID. # Corrected indentation (4 spaces)

    Args: # Corrected indentation (4 spaces)
        agent_id: The unique ID for the agent (provided by AgentKit). # Corrected indentation (8 spaces)
        details: Pydantic model containing agent metadata (name, version, etc.). # Corrected indentation (8 spaces)

    Returns: # Corrected indentation (4 spaces)
        The AgentInfo object representing the registered agent. # Corrected indentation (8 spaces)

    Raises: # Corrected indentation (4 spaces)
        pydantic.ValidationError: If agent_details are invalid. # Corrected indentation (8 spaces)
        exceptions.RegistrationError: If storage fails during registration. # Corrected indentation (8 spaces)
    """ # Corrected indentation (4 spaces)
    agent_name = details.agentName # Corrected indentation (4 spaces)
    logger.info(f"Attempting to register agent: {agent_name} with ID: {agent_id}") # Corrected indentation (4 spaces)

    # Validate agent_id format? (Optional, assume valid string for now) # Corrected indentation (4 spaces)
    if not agent_id: # Corrected indentation (4 spaces)
        raise ValueError("agent_id cannot be empty") # Corrected indentation (8 spaces)

    # Create the full AgentInfo object using provided ID and details # Corrected indentation (4 spaces)
    try: # Corrected indentation (4 spaces)
        agent_info = AgentInfo( # Corrected indentation (8 spaces)
            **details.model_dump(), # Spread the details (includes agentId)
            registrationTime=datetime.now(timezone.utc) # Set registration time to now
        ) # Corrected indentation (8 spaces)
    except Exception as e: # Catch potential Pydantic validation errors # Corrected indentation (4 spaces)
        logger.error(f"Failed to create AgentInfo model for agent {agent_id}: {e}", exc_info=True) # Corrected indentation (8 spaces)
        # Use a more specific exception if available, or re-raise validation error # Corrected indentation (8 spaces)
        raise exceptions.RegistrationError(f"Invalid agent details provided for {agent_id}", original_exception=e) from e # Corrected indentation (8 spaces)

    # Store agent registration data using the storage module # Corrected indentation (4 spaces)
    try: # Corrected indentation (4 spaces)
        storage.save_agent_registration(agent_info) # Corrected indentation (8 spaces)
        logger.info(f"Agent '{agent_name}' registration data saved successfully with ID: {agent_id}") # Corrected indentation (8 spaces)

        # Set initial state after successful registration storage # Corrected indentation (8 spaces)
        try: # Corrected indentation (8 spaces)
            set_state(agent_id=agent_id, new_state="UNKNOWN", details={"reason": "Initial registration"}) # Corrected indentation (12 spaces)
            logger.info(f"Initial state 'UNKNOWN' set for agent {agent_id}") # Corrected indentation (12 spaces)
        except Exception as state_e: # Corrected indentation (8 spaces)
            # Log error setting initial state, but don't fail the registration itself? # Corrected indentation (12 spaces)
            # Or should we attempt to rollback/delete the registration? # Corrected indentation (12 spaces)
            # For now, log error and continue. Consider cleanup later. # Corrected indentation (12 spaces)
            logger.error(f"Failed to set initial state for newly registered agent {agent_id}: {state_e}", exc_info=True) # Corrected indentation (12 spaces)
            # Optionally raise a specific warning/error or just proceed # Corrected indentation (12 spaces)

    except exceptions.AgentAlreadyExistsError as e: # Catch specific error from storage # Corrected indentation (4 spaces)
        logger.warning(f"Attempted to register agent {agent_id} which already exists.") # Corrected indentation (8 spaces)
        raise e # Re-raise for the API layer to handle # Corrected indentation (8 spaces)
    except Exception as e: # Corrected indentation (4 spaces)
        logger.error(f"Failed to save registration for agent {agent_id}: {e}", exc_info=True) # Corrected indentation (8 spaces)
        raise exceptions.RegistrationError(f"Failed to save registration for agent {agent_id}", original_exception=e) from e

    return agent_info

# --- State Management ---

def set_state(agent_id: str, new_state: str, details: Optional[Dict[str, Any]] = None, timestamp: Optional[str] = None):
    """
    Updates the state of a registered agent.

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
    logger.info(f"Setting state for agent {agent_id} to '{new_state}'")
    # Validate agent_id exists using storage module (read operation)
    if not storage.read_agent_registration(agent_id):
        logger.error(f"Attempted to set state for unknown agent ID: {agent_id}")
        raise exceptions.AgentNotFoundError(agent_id)

    # TODO: Validate new_state against allowed states (defined in models?)

    # TODO: Parse timestamp string to datetime object if provided
    state_timestamp = datetime.now(timezone.utc) # Default to now (timezone-aware)
    if timestamp:
        try:
            # Attempt to parse timestamp, fallback to now if invalid
            # Ensure timezone awareness if needed, Pydantic might handle this better
            state_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Invalid timestamp format received for agent {agent_id}: '{timestamp}'. Using current time.")
            # Keep state_timestamp as datetime.utcnow()

    # Create state update object using the Pydantic model
    try:
        agent_state = AgentState(
            agentId=agent_id,
            state=new_state,
            details=details,
            timestamp=state_timestamp
        )
    except Exception as e: # Catch potential Pydantic validation errors
        logger.error(f"Failed to create AgentState model for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.InvalidStateError(f"Invalid state data provided: {e}") from e

    # Store the state update using the storage module
    try:
        storage.save_agent_state(agent_state)
        logger.info(f"State for agent {agent_id} updated to '{new_state}'")
    except Exception as e:
        logger.error(f"Failed to save state for agent {agent_id} to storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id}", original_exception=e) from e


def get_state(agent_id: str) -> Optional[AgentState]:
    """
    Retrieves the current state of a registered agent.

    Args:
        agent_id: The ID of the agent.

    Returns:
        An AgentState object representing the agent's current state,
        or None if the agent or state is not found.
    """
    logger.debug(f"Fetching state for agent {agent_id}")
    # Retrieve state from storage module
    agent_state = storage.read_latest_agent_state(agent_id)
    if agent_state:
        logger.debug(f"Found state for agent {agent_id}: {agent_state.state}")
        return agent_state
    else:
        logger.warning(f"No state found for agent {agent_id}")
        return None

# --- Session Management ---

def start_session(agent_id: str, workflow_id: str) -> WorkflowSession:
    """
    Starts a new workflow session for an agent.

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
    logger.info(f"Attempting to start new session for agent {agent_id}, workflow {workflow_id}")

    # Validate agent_id exists
    if not storage.read_agent_registration(agent_id):
        logger.error(f"Cannot start session: Agent {agent_id} not found.")
        raise exceptions.AgentNotFoundError(agent_id)

    # Create session object (generates its own ID and timestamps)
    try:
        session = WorkflowSession(
            agentId=agent_id,
            workflowId=workflow_id,
            # sessionId, startTime, last_updated_time, status are handled by model defaults
        )
    except Exception as e: # Should not happen with these args, but good practice
        logger.error(f"Failed to create WorkflowSession model: {e}", exc_info=True)
        raise exceptions.OpsCoreError(f"Failed to initialize session object: {e}") from e

    # Store session data using storage module
    try:
        storage.create_session(session)
        logger.info(f"Session {session.sessionId} started successfully for agent {agent_id}, workflow {workflow_id}")
    except ValueError as e: # Catch potential duplicate ID error from storage
        logger.error(f"Failed to create session in storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to create session: {e}", original_exception=e) from e
    except Exception as e:
        logger.error(f"Failed to save session {session.sessionId} to storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save session {session.sessionId}", original_exception=e) from e

    return session

def update_session(session_id: str, update_payload: SessionUpdate) -> WorkflowSession:
    """
    Updates an existing workflow session using provided data.

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
    logger.info(f"Attempting to update session {session_id}")

    # Prepare update dictionary, only including fields explicitly set in the payload
    update_dict = update_payload.model_dump(exclude_unset=True)

    if not update_dict:
        logger.warning(f"Update called for session {session_id} with no changes provided.")
        # Optionally return the existing session without hitting storage
        existing_session = storage.read_session(session_id)
        if not existing_session:
             raise exceptions.SessionNotFoundError(session_id)
        return existing_session


    # Always update the last_updated_time
    update_dict['last_updated_time'] = datetime.now(timezone.utc) # Use timezone-aware

    # If status is changing to a terminal state, set endTime if not already set
    if 'status' in update_dict and update_dict['status'] in ['completed', 'failed', 'cancelled']:
        if 'endTime' not in update_dict: # Only set if not explicitly provided
            update_dict['endTime'] = datetime.now(timezone.utc) # Use timezone-aware

    logger.debug(f"Applying updates to session {session_id}: {update_dict}")

    try:
        updated_session = storage.update_session_data(session_id, update_dict)
        logger.info(f"Session {session_id} updated successfully.")
        return updated_session
    except KeyError: # Raised by storage.update_session_data if session_id not found
        logger.error(f"Update failed: Session {session_id} not found.")
        raise exceptions.SessionNotFoundError(session_id)
    except ValueError as e: # Raised by storage.update_session_data for invalid data
        logger.error(f"Update failed for session {session_id} due to invalid data: {e}", exc_info=True)
        raise exceptions.InvalidStateError(f"Invalid update data for session {session_id}: {e}") from e
    except Exception as e:
        logger.error(f"Failed to update session {session_id} in storage: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to update session {session_id}", original_exception=e) from e


def get_session(session_id: str) -> Optional[WorkflowSession]:
    """
    Retrieves details of a specific workflow session.

    Args:
        session_id: The ID of the session.

    Returns:
        A WorkflowSession object representing the session data, or None if not found.
    """
    logger.debug(f"Fetching session details for {session_id}")
    session = storage.read_session(session_id)
    if session:
        logger.debug(f"Found session {session_id}")
    else:
        logger.warning(f"No session found for ID: {session_id}")
    return session