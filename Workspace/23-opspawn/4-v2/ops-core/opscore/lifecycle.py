"""
Ops-Core Lifecycle Management Subsystem

Handles agent registration, state tracking, and session management.
"""

import uuid # Import uuid module
from datetime import datetime, timezone # Import timezone
from typing import Dict, Any, Optional, List

# Placeholder imports - replace with actual implementations
from . import storage
from .models import AgentInfo, AgentRegistrationDetails, AgentState, WorkflowSession, SessionUpdate
# from . import exceptions # TODO: Define custom exceptions later
from .logging_config import get_logger

logger = get_logger(__name__)

# --- Agent Registration ---

def register_agent(agent_details: AgentRegistrationDetails) -> AgentInfo:
    """
    Registers a new agent with Ops-Core.

    Args:
        agent_details: Pydantic model containing agent metadata.

    Returns:
        The AgentInfo object representing the registered agent.

    Raises:
        ValueError: If agent_details are invalid (handled by Pydantic).
        IOError: If storage fails.
        # exceptions.RegistrationError: If registration fails.
    """
    agent_name = agent_details.agentName
    logger.info(f"Attempting to register agent: {agent_name}")

    # Generate a unique agent ID
    agent_id = f"agent_{uuid.uuid4()}"

    # Create the full AgentInfo object including generated ID and timestamp
    # Pydantic validation happens implicitly if agent_details is already the correct type
    agent_info = AgentInfo(
        **agent_details.model_dump(),
        agentId=agent_id,
        registrationTime=datetime.now(timezone.utc) # Use timezone-aware
    )

    # Store agent registration data using the storage module
    try:
        storage.save_agent_registration(agent_info)
        logger.info(f"Agent '{agent_name}' registered successfully with ID: {agent_id}")
    except Exception as e:
        logger.error(f"Failed to save registration for agent {agent_id}: {e}", exc_info=True)
        # TODO: Define a specific registration/storage exception?
        raise IOError(f"Failed to save registration for agent {agent_id}") from e

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
        # exceptions.AgentNotFoundError: If the agent_id is not found.
        # exceptions.InvalidStateError: If the new_state is not a valid state.
    """
    logger.info(f"Setting state for agent {agent_id} to '{new_state}'")
    # Validate agent_id exists using storage module (read operation)
    if not storage.read_agent_registration(agent_id):
        logger.error(f"Attempted to set state for unknown agent ID: {agent_id}")
        # raise exceptions.AgentNotFoundError(agent_id) # TODO: Use custom exception
        raise ValueError(f"Agent not found: {agent_id}")

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
        raise ValueError(f"Invalid state data provided: {e}") from e

    # Store the state update using the storage module
    try:
        storage.save_agent_state(agent_state)
        logger.info(f"State for agent {agent_id} updated to '{new_state}'")
    except Exception as e:
        logger.error(f"Failed to save state for agent {agent_id} to storage: {e}", exc_info=True)
        # TODO: Define a specific storage exception?
        raise IOError(f"Failed to save state for agent {agent_id}") from e


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
        ValueError: If the agent_id is not found or session creation fails.
        IOError: If storage fails.
        # exceptions.AgentNotFoundError: If the agent_id is not found.
    """
    logger.info(f"Attempting to start new session for agent {agent_id}, workflow {workflow_id}")

    # Validate agent_id exists
    if not storage.read_agent_registration(agent_id):
        logger.error(f"Cannot start session: Agent {agent_id} not found.")
        raise ValueError(f"Agent not found: {agent_id}")

    # Create session object (generates its own ID and timestamps)
    try:
        session = WorkflowSession(
            agentId=agent_id,
            workflowId=workflow_id,
            # sessionId, startTime, last_updated_time, status are handled by model defaults
        )
    except Exception as e: # Should not happen with these args, but good practice
        logger.error(f"Failed to create WorkflowSession model: {e}", exc_info=True)
        raise ValueError(f"Failed to initialize session object: {e}") from e

    # Store session data using storage module
    try:
        storage.create_session(session)
        logger.info(f"Session {session.sessionId} started successfully for agent {agent_id}, workflow {workflow_id}")
    except ValueError as e: # Catch potential duplicate ID error from storage
        logger.error(f"Failed to create session in storage: {e}", exc_info=True)
        raise ValueError(f"Failed to create session: {e}") from e
    except Exception as e:
        logger.error(f"Failed to save session {session.sessionId} to storage: {e}", exc_info=True)
        raise IOError(f"Failed to save session {session.sessionId}") from e

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
        ValueError: If the session_id is not found or update data is invalid.
        IOError: If storage fails.
        # exceptions.SessionNotFoundError: If the session_id is not found.
    """
    logger.info(f"Attempting to update session {session_id}")

    # Prepare update dictionary, only including fields explicitly set in the payload
    update_dict = update_payload.model_dump(exclude_unset=True)

    if not update_dict:
        logger.warning(f"Update called for session {session_id} with no changes provided.")
        # Optionally return the existing session without hitting storage
        existing_session = storage.read_session(session_id)
        if not existing_session:
             raise ValueError(f"Session not found: {session_id}")
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
        raise ValueError(f"Session not found: {session_id}")
    except ValueError as e: # Raised by storage.update_session_data for invalid data
        logger.error(f"Update failed for session {session_id} due to invalid data: {e}", exc_info=True)
        raise ValueError(f"Invalid update data for session {session_id}: {e}") from e
    except Exception as e:
        logger.error(f"Failed to update session {session_id} in storage: {e}", exc_info=True)
        raise IOError(f"Failed to update session {session_id}") from e


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