"""
Ops-Core Storage Subsystem (In-Memory Implementation)

Provides an abstraction layer for persisting and retrieving Ops-Core data,
such as agent registrations, states, sessions, and workflow definitions.

This initial implementation uses simple Python dictionaries for in-memory storage.
It should be replaced with a more robust persistent storage solution (e.g., Redis, DB)
in later phases.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone # Already imported
import threading

from .models import AgentInfo, AgentState, WorkflowDefinition, WorkflowSession
from . import exceptions # Import custom exceptions
from .logging_config import get_logger

logger = get_logger(__name__)

# --- In-Memory Data Stores ---
# Using thread-safe locks for basic safety, although a proper DB/Redis handles concurrency better.

_agent_registrations: Dict[str, Dict[str, Any]] = {}
_agent_registrations_lock = threading.Lock()

_agent_states: Dict[str, List[Dict[str, Any]]] = {} # Store history, latest is last element
_agent_states_lock = threading.Lock()

_sessions: Dict[str, WorkflowSession] = {}
_sessions_lock = threading.Lock()

_workflow_definitions: Dict[str, Dict[str, Any]] = {}
_workflow_definitions_lock = threading.Lock()

# --- Agent Registration ---

def save_agent_registration(agent_info: AgentInfo):
    """Saves agent registration details."""
    agent_id = agent_info.agentId
    logger.debug(f"Saving registration for agent {agent_id}")
    try:
        with _agent_registrations_lock:
            # Store as dict for simplicity in this in-memory version
            _agent_registrations[agent_id] = agent_info.model_dump(mode='json')
            logger.info(f"Registration saved for agent {agent_id}")
    except (TypeError, ValueError) as e: # Catch specific data errors outside lock if model_dump fails, though unlikely
        logger.error(f"Data error preparing agent registration for {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save registration for agent {agent_id} due to data issue", original_exception=e) from e
    except Exception as e: # Catch lock errors or other unexpected issues
        logger.error(f"Unexpected error saving registration for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save registration for agent {agent_id}", original_exception=e) from e

def read_agent_registration(agent_id: str) -> Optional[AgentInfo]:
    """Retrieves agent registration details."""
    logger.debug(f"Retrieving registration for agent {agent_id}")
    with _agent_registrations_lock:
        data_dict = _agent_registrations.get(agent_id)
    if data_dict:
        logger.debug(f"Found registration for agent {agent_id}")
        try:
            return AgentInfo(**data_dict)
        except Exception as e: # Handle potential Pydantic validation errors
             logger.error(f"Failed to parse stored registration data for agent {agent_id}: {e}")
             return None
    else:
        logger.warning(f"No registration found for agent {agent_id}")
        return None

def agent_exists(agent_id: str) -> bool:
    """Checks if an agent registration exists."""
    with _agent_registrations_lock:
        exists = agent_id in _agent_registrations
    logger.debug(f"Checking existence for agent {agent_id}: {exists}")
    return exists

def get_all_agent_registrations() -> List[AgentInfo]:
    """Retrieves all agent registration details."""
    logger.debug("Retrieving all agent registrations")
    agents = []
    with _agent_registrations_lock:
        agent_dicts = list(_agent_registrations.values())

    for data_dict in agent_dicts:
        try:
            agents.append(AgentInfo(**data_dict))
        except Exception as e:
            agent_id = data_dict.get('agentId', 'UNKNOWN')
            logger.error(f"Failed to parse stored registration data for agent {agent_id}: {e}")
            # Optionally skip corrupted entries or handle differently

    logger.debug(f"Found {len(agents)} valid agent registrations.")
    return agents

# --- Agent State ---

def save_agent_state(agent_state: AgentState):
    """Saves an agent state update (appends to history)."""
    agent_id = agent_state.agentId
    logger.debug(f"Saving state for agent {agent_id}: {agent_state.state}")
    try:
        with _agent_states_lock:
            if agent_id not in _agent_states:
                _agent_states[agent_id] = []
            # Store as dict for simplicity in this in-memory version
            _agent_states[agent_id].append(agent_state.model_dump(mode='json'))
            # Optional: Limit history size if needed
            # MAX_HISTORY = 100
            # if len(_agent_states[agent_id]) > MAX_HISTORY:
            #     logger.debug(f"Trimming state history for agent {agent_id}")
            #     _agent_states[agent_id] = _agent_states[agent_id][-MAX_HISTORY:]
            logger.info(f"State saved for agent {agent_id}")
    except (TypeError, ValueError) as e: # Catch specific data errors (e.g., model_dump)
        logger.error(f"Data error during agent state save for {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id} due to data issue", original_exception=e) from e
    except Exception as e: # Catch lock errors or other unexpected issues
        logger.error(f"Unexpected error saving state for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id}", original_exception=e) from e

def read_latest_agent_state(agent_id: str) -> Optional[AgentState]:
    """Retrieves the most recent state for an agent."""
    logger.debug(f"Retrieving latest state for agent {agent_id}")
    with _agent_states_lock:
        history = _agent_states.get(agent_id)
        if history:
            latest_state_dict = history[-1]
            logger.debug(f"Found latest state dict for agent {agent_id}")
            try:
                return AgentState(**latest_state_dict)
            except Exception as e:
                logger.error(f"Failed to parse stored state data for agent {agent_id}: {e}")
                return None
        else:
            logger.warning(f"No state history found for agent {agent_id}")
            return None

def read_agent_state_history(agent_id: str) -> List[AgentState]:
    """Retrieves the full state history for an agent."""
    logger.debug(f"Retrieving state history for agent {agent_id}")
    states = []
    with _agent_states_lock:
        # Get a copy of the list of dicts
        history_dicts = list(_agent_states.get(agent_id, []))

    for state_dict in history_dicts:
        try:
            states.append(AgentState(**state_dict))
        except Exception as e:
            logger.error(f"Failed to parse stored state data for agent {agent_id} in history: {e}")
            # Optionally skip corrupted entries

    logger.debug(f"Found {len(states)} valid state entries for agent {agent_id}")
    return states

# --- Workflow Session ---

def create_session(session: WorkflowSession) -> None:
    """Creates and saves a new workflow session."""
    session_id = session.sessionId
    logger.debug(f"Attempting to create session {session_id}")
    try:
        with _sessions_lock:
            if session_id in _sessions:
                logger.error(f"Session creation failed: Session ID {session_id} already exists.")
                # Raise a specific storage error for duplicate keys
                raise exceptions.StorageError(f"Session ID {session_id} already exists.")
            # Store the model directly
            _sessions[session_id] = session
            logger.info(f"Session {session_id} created successfully.")
    except (TypeError, ValueError) as e: # Catch specific data errors (less likely here)
        logger.error(f"Data error during session creation for {session_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to create session {session_id} due to data issue", original_exception=e) from e
    except Exception as e: # Catch lock errors or other unexpected issues
        logger.error(f"Unexpected error creating session {session_id}: {e}", exc_info=True)
        # Check if it's the duplicate key StorageError we already raised inside the 'with'
        if isinstance(e, exceptions.StorageError) and "already exists" in str(e):
             raise e # Re-raise the specific duplicate key error
        # Otherwise, wrap other exceptions as a general StorageError
        raise exceptions.StorageError(f"Failed to create session {session_id}", original_exception=e) from e

def read_session(session_id: str) -> Optional[WorkflowSession]:
    """Retrieves workflow session data by ID."""
    logger.debug(f"Retrieving session {session_id}")
    with _sessions_lock:
        # Return a copy to prevent external modification? For models, maybe not necessary
        # unless internal state can be mutated. Pydantic models are generally immutable-like.
        session = _sessions.get(session_id)
    if session:
        logger.debug(f"Found session {session_id}")
    else:
        logger.warning(f"Session {session_id} not found.")
    return session

def update_session_data(session_id: str, update_data: Dict[str, Any]) -> WorkflowSession:
    """
    Updates specific fields of an existing workflow session.

    Args:
        session_id: The ID of the session to update.
        update_data: A dictionary containing the fields to update.
                     Must include 'last_updated_time'.

    Returns:
        The updated WorkflowSession object.

    Raises:
        exceptions.SessionNotFoundError: If the session_id is not found.
        exceptions.InvalidStateError: If update_data results in an invalid session state.
        exceptions.StorageError: If there's an issue saving the updated session.
    """
    logger.debug(f"Attempting to update session {session_id} with data: {update_data}")
    try:
        with _sessions_lock:
            if session_id not in _sessions:
                logger.error(f"Update failed: Session {session_id} not found.")
                raise exceptions.SessionNotFoundError(session_id)

            existing_session = _sessions[session_id]

            # Create a new session object with updated fields
            # This leverages Pydantic's validation on update
            try:
                # Use model_copy for safe updates if available and appropriate
                # For now, dictionary update and re-validation
                updated_session_data = existing_session.model_dump()
                updated_session_data.update(update_data)
                # Ensure last_updated_time is always set by the caller or here
                if 'last_updated_time' not in update_data:
                     updated_session_data['last_updated_time'] = datetime.now(timezone.utc) # Use timezone-aware

                updated_session = WorkflowSession(**updated_session_data)
                _sessions[session_id] = updated_session # Replace the old session object
                logger.info(f"Session {session_id} updated successfully.")
                return updated_session
            except ValueError as e: # Catch Pydantic validation errors specifically
                logger.error(f"Failed to update session {session_id} due to invalid data: {e}", exc_info=True)
                # Re-raise the specific InvalidStateError caught from Pydantic validation
                raise exceptions.InvalidStateError(f"Invalid update data for session {session_id}: {e}") from e
            # No need for broad except Exception here, as it's caught outside the 'with' block

    except Exception as e: # Catch lock errors or other unexpected issues during the update process
        logger.error(f"Unexpected error updating session {session_id}: {e}", exc_info=True)
        # Avoid wrapping SessionNotFoundError or InvalidStateError again
        if not isinstance(e, (exceptions.SessionNotFoundError, exceptions.InvalidStateError)):
            raise exceptions.StorageError(f"Failed to update session {session_id}", original_exception=e) from e
        else:
            raise e # Re-raise the specific caught exceptions

def delete_session(session_id: str) -> bool:
    """Deletes a workflow session by ID."""
    logger.debug(f"Attempting to delete session {session_id}")
    with _sessions_lock:
        if session_id in _sessions:
            del _sessions[session_id]
            logger.info(f"Session {session_id} deleted successfully.")
            return True
        else:
            logger.warning(f"Delete failed: Session {session_id} not found.")
            return False

# --- Workflow Definition ---

def save_workflow_definition(definition: WorkflowDefinition):
    """Saves a workflow definition."""
    workflow_id = definition.id
    logger.debug(f"Saving workflow definition {workflow_id}")
    try:
        with _workflow_definitions_lock:
            # Store as dict
            _workflow_definitions[workflow_id] = definition.model_dump(mode='json')
            logger.info(f"Workflow definition {workflow_id} saved.")
    except (TypeError, ValueError) as e: # Catch specific data errors (e.g., model_dump)
        logger.error(f"Data error saving workflow definition {workflow_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id} due to data issue", original_exception=e) from e
    except Exception as e: # Catch lock errors or other unexpected issues
        logger.error(f"Unexpected error saving workflow definition {workflow_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id}", original_exception=e) from e

def read_workflow_definition(workflow_id: str) -> Optional[WorkflowDefinition]:
    """Retrieves a workflow definition."""
    logger.debug(f"Retrieving workflow definition {workflow_id}")
    with _workflow_definitions_lock:
        data_dict = _workflow_definitions.get(workflow_id)
    if data_dict:
        logger.debug(f"Found workflow definition {workflow_id}")
        try:
            return WorkflowDefinition(**data_dict)
        except Exception as e:
            logger.error(f"Failed to parse stored workflow definition {workflow_id}: {e}")
            return None
    else:
        logger.warning(f"Workflow definition {workflow_id} not found.")
        return None

# --- Utility ---
def clear_all_data():
    """Clears all in-memory data (useful for testing)."""
    logger.warning("Clearing all in-memory storage.")
    with _agent_registrations_lock:
        _agent_registrations.clear()
    with _agent_states_lock:
        _agent_states.clear()
    with _sessions_lock:
        _sessions.clear()
    with _workflow_definitions_lock:
        _workflow_definitions.clear()
    logger.info("In-memory storage cleared.")