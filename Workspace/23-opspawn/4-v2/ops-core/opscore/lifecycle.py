"""
Ops-Core Lifecycle Management Subsystem

Handles agent registration, state tracking, and session management.
"""

import uuid # Import uuid module
from datetime import datetime
from typing import Dict, Any, Optional

# Placeholder imports - replace with actual implementations
from . import storage, models # Import storage and models
# from . import exceptions # TODO: Define custom exceptions later
from .logging_config import get_logger

logger = get_logger(__name__)

# --- Agent Registration ---

def register_agent(agent_details: Dict[str, Any]) -> str:
    """
    Registers a new agent with Ops-Core.

    Args:
        agent_details: Dictionary containing agent metadata (e.g., name, capabilities, contactEndpoint).

    Returns:
        The unique agent ID assigned to the registered agent.

    Raises:
        # exceptions.RegistrationError: If registration fails.
    """
    logger.info(f"Attempting to register agent: {agent_details.get('agentName', 'N/A')}")
    # Generate a unique agent ID
    agent_id = f"agent_{uuid.uuid4()}"

    # Validate agent_details against the Pydantic model
    try:
        # We expect the input details to match AgentRegistrationDetails
        validated_details = models.AgentRegistrationDetails(**agent_details)
    except Exception as e: # Catch Pydantic validation errors
        logger.error(f"Invalid agent registration details provided: {e}", exc_info=True)
        raise ValueError(f"Invalid agent registration details: {e}")

    # Create the full AgentInfo object including generated ID and timestamp
    registration_data = models.AgentInfo(
        **validated_details.model_dump(),
        agentId=agent_id,
        registrationTime=datetime.utcnow()
    )

    # Store agent registration data using the storage module
    try:
        storage.save_agent_registration(agent_id, registration_data.model_dump())
        logger.info(f"Agent '{validated_details.agentName}' registered successfully with ID: {agent_id}")
    except Exception as e:
        logger.error(f"Failed to save registration for agent {agent_id}: {e}", exc_info=True)
        # TODO: Define a specific registration/storage exception?
        raise IOError(f"Failed to save registration for agent {agent_id}")

    return agent_id

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
    # Validate agent_id exists using storage module
    if not storage.agent_exists(agent_id):
        logger.error(f"Attempted to set state for unknown agent ID: {agent_id}")
        # raise exceptions.AgentNotFoundError(agent_id) # TODO: Use custom exception
        raise ValueError(f"Agent not found: {agent_id}")

    # TODO: Validate new_state against allowed states (defined in models?)

    # TODO: Parse timestamp string to datetime object if provided
    state_timestamp = datetime.utcnow() # Default to now
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
        state_data = models.AgentState(
            agentId=agent_id,
            state=new_state,
            details=details,
            timestamp=state_timestamp
        )
    except Exception as e: # Catch potential Pydantic validation errors
        logger.error(f"Failed to create AgentState model for agent {agent_id}: {e}", exc_info=True)
        raise ValueError(f"Invalid state data provided: {e}")

    # Store the state update using the storage module
    try:
        # Use .model_dump() for Pydantic v2+
        storage.save_agent_state(agent_id, state_data.model_dump())
        logger.info(f"State for agent {agent_id} updated to '{new_state}'")
    except Exception as e:
        logger.error(f"Failed to save state for agent {agent_id} to storage: {e}", exc_info=True)
        # TODO: Define a specific storage exception?
        raise IOError(f"Failed to save state for agent {agent_id}")

    # print(f"Placeholder: Set state for {agent_id} to {new_state} at {timestamp or 'now'} with details: {details}") # Placeholder print


def get_state(agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the current state of a registered agent.

    Args:
        agent_id: The ID of the agent.

    Returns:
        A dictionary representing the agent's current state (e.g., from models.AgentState),
        or None if the agent or state is not found.
    """
    logger.debug(f"Fetching state for agent {agent_id}")
    # Retrieve state from storage module
    state_data = storage.get_latest_agent_state(agent_id)
    if state_data:
        # TODO: Consider returning a Pydantic model (models.AgentState) instead of dict?
        logger.debug(f"Found state for agent {agent_id}: {state_data.get('state')}")
        return state_data
    else:
        logger.warning(f"No state found for agent {agent_id}")
        return None
    # return {"agentId": agent_id, "state": "unknown", "timestamp": datetime.utcnow().isoformat()} # Placeholder return

# --- Session Management ---

def start_session(agent_id: str, workflow_id: str) -> str:
    """
    Starts a new workflow session for an agent.

    Args:
        agent_id: The ID of the agent involved in the session.
        workflow_id: The ID of the workflow being executed.

    Returns:
        The unique session ID created for this workflow execution.

    Raises:
        # exceptions.AgentNotFoundError: If the agent_id is not found.
    """
    logger.info(f"Starting new session for agent {agent_id}, workflow {workflow_id}")
    # TODO: Validate agent_id exists

    session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S%f')}" # Simple placeholder ID
    start_time = datetime.utcnow()

    # TODO: Create session object (models.WorkflowSession)
    # session_data = models.WorkflowSession(
    #     sessionId=session_id,
    #     agentId=agent_id,
    #     workflowId=workflow_id,
    #     startTime=start_time,
    #     status="started" # Initial status
    # )

    # TODO: Store session data using storage module
    # storage.save_session(session_id, session_data.dict())
    logger.info(f"Session {session_id} started for agent {agent_id}, workflow {workflow_id}") # Placeholder logic

    # print(f"Placeholder: Started session {session_id} for agent {agent_id}, workflow {workflow_id}") # Placeholder print
    return session_id

def update_session(agent_id: str, session_id: str, changes: Dict[str, Any]):
    """
    Updates an existing workflow session.

    Args:
        agent_id: The ID of the agent (for verification).
        session_id: The ID of the session to update.
        changes: A dictionary containing updates (e.g., {"status": "completed", "endTime": ..., "result": ...}).

    Raises:
        # exceptions.SessionNotFoundError: If the session_id is not found.
        # exceptions.AuthorizationError: If the agent_id doesn't match the session's agent.
    """
    logger.info(f"Updating session {session_id} for agent {agent_id} with changes: {changes}")
    # TODO: Retrieve session data from storage
    # session_data = storage.get_session(session_id)
    # if not session_data:
    #     logger.error(f"Attempted to update unknown session ID: {session_id}")
    #     raise exceptions.SessionNotFoundError(session_id)

    # TODO: Verify agent_id matches session_data['agentId']
    # if session_data['agentId'] != agent_id:
    #     logger.error(f"Agent {agent_id} attempted to update session {session_id} belonging to agent {session_data['agentId']}")
    #     raise exceptions.AuthorizationError("Agent ID does not match session owner")

    # TODO: Apply changes to session_data
    # session_data.update(changes)
    # if 'endTime' not in changes and changes.get('status') in ['completed', 'failed', 'cancelled']:
    #     session_data['endTime'] = datetime.utcnow()

    # TODO: Save updated session data back to storage
    # storage.save_session(session_id, session_data)
    logger.info(f"Session {session_id} updated successfully.") # Placeholder logic

    # print(f"Placeholder: Updated session {session_id} with changes: {changes}") # Placeholder print

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves details of a specific workflow session.

    Args:
        session_id: The ID of the session.

    Returns:
        A dictionary representing the session data, or None if not found.
    """
    # logger.debug(f"Fetching session details for {session_id}")
    # TODO: Retrieve session from storage module
    # session_data = storage.get_session(session_id)
    # if session_data:
    #     logger.debug(f"Found session {session_id}")
    #     return session_data
    # else:
    #     logger.warning(f"No session found for ID: {session_id}")
    #     return None
    # print(f"Placeholder: Get session {session_id}") # Placeholder print
    return {"sessionId": session_id, "status": "unknown"} # Placeholder return