"""
Ops-Core Storage Subsystem (In-Memory Implementation)

Provides an abstraction layer for persisting and retrieving Ops-Core data,
such as agent registrations, states, sessions, and workflow definitions.

This initial implementation uses simple Python dictionaries for in-memory storage.
It should be replaced with a more robust persistent storage solution (e.g., Redis, DB)
in later phases.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

# Placeholder imports - replace with actual implementations
# from . import models, exceptions
from .logging_config import get_logger

logger = get_logger(__name__)

# --- In-Memory Data Stores ---
# Using thread-safe locks for basic safety, although a proper DB/Redis handles concurrency better.

_agent_registrations: Dict[str, Dict[str, Any]] = {}
_agent_registrations_lock = threading.Lock()

_agent_states: Dict[str, List[Dict[str, Any]]] = {} # Store history, latest is last element
_agent_states_lock = threading.Lock()

_workflow_sessions: Dict[str, Dict[str, Any]] = {}
_workflow_sessions_lock = threading.Lock()

_workflow_definitions: Dict[str, Dict[str, Any]] = {}
_workflow_definitions_lock = threading.Lock()

# --- Agent Registration ---

def save_agent_registration(agent_id: str, registration_data: Dict[str, Any]):
    """Saves agent registration details."""
    logger.debug(f"Saving registration for agent {agent_id}")
    with _agent_registrations_lock:
        _agent_registrations[agent_id] = registration_data
    logger.info(f"Registration saved for agent {agent_id}")

def get_agent_registration(agent_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves agent registration details."""
    logger.debug(f"Retrieving registration for agent {agent_id}")
    with _agent_registrations_lock:
        data = _agent_registrations.get(agent_id)
    if data:
        logger.debug(f"Found registration for agent {agent_id}")
    else:
        logger.warning(f"No registration found for agent {agent_id}")
    return data

def agent_exists(agent_id: str) -> bool:
    """Checks if an agent registration exists."""
    with _agent_registrations_lock:
        exists = agent_id in _agent_registrations
    logger.debug(f"Checking existence for agent {agent_id}: {exists}")
    return exists

def get_all_agent_registrations() -> List[Dict[str, Any]]:
    """Retrieves all agent registration details."""
    logger.debug("Retrieving all agent registrations")
    with _agent_registrations_lock:
        all_regs = list(_agent_registrations.values())
    logger.debug(f"Found {len(all_regs)} agent registrations.")
    return all_regs

# --- Agent State ---

def save_agent_state(agent_id: str, state_data: Dict[str, Any]):
    """Saves an agent state update (appends to history)."""
    logger.debug(f"Saving state for agent {agent_id}: {state_data.get('state')}")
    with _agent_states_lock:
        if agent_id not in _agent_states:
            _agent_states[agent_id] = []
        _agent_states[agent_id].append(state_data)
        # Optional: Limit history size if needed
        # MAX_HISTORY = 100
        # if len(_agent_states[agent_id]) > MAX_HISTORY:
        #     logger.debug(f"Trimming state history for agent {agent_id}")
        #     _agent_states[agent_id] = _agent_states[agent_id][-MAX_HISTORY:]
    logger.info(f"State saved for agent {agent_id}")

def get_latest_agent_state(agent_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the most recent state for an agent."""
    logger.debug(f"Retrieving latest state for agent {agent_id}")
    with _agent_states_lock:
        history = _agent_states.get(agent_id)
        if history:
            latest_state = history[-1]
            logger.debug(f"Found latest state for agent {agent_id}: {latest_state.get('state')}")
            return latest_state
        else:
            logger.warning(f"No state history found for agent {agent_id}")
            return None

def get_agent_state_history(agent_id: str) -> List[Dict[str, Any]]:
    """Retrieves the full state history for an agent."""
    logger.debug(f"Retrieving state history for agent {agent_id}")
    with _agent_states_lock:
        # Return a copy to prevent external modification of the internal list
        history = list(_agent_states.get(agent_id, []))
    logger.debug(f"Found {len(history)} state entries for agent {agent_id}")
    return history

# --- Workflow Session ---

def save_session(session_id: str, session_data: Dict[str, Any]):
    """Saves or updates workflow session data."""
    logger.debug(f"Saving session {session_id}")
    with _workflow_sessions_lock:
        _workflow_sessions[session_id] = session_data
    logger.info(f"Session {session_id} saved.")

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves workflow session data."""
    logger.debug(f"Retrieving session {session_id}")
    with _workflow_sessions_lock:
        data = _workflow_sessions.get(session_id)
    if data:
        logger.debug(f"Found session {session_id}")
    else:
        logger.warning(f"Session {session_id} not found.")
    return data

# --- Workflow Definition ---

def save_workflow_definition(workflow_id: str, definition_data: Dict[str, Any]):
    """Saves a workflow definition."""
    logger.debug(f"Saving workflow definition {workflow_id}")
    with _workflow_definitions_lock:
        _workflow_definitions[workflow_id] = definition_data
    logger.info(f"Workflow definition {workflow_id} saved.")

def get_workflow_definition(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a workflow definition."""
    logger.debug(f"Retrieving workflow definition {workflow_id}")
    with _workflow_definitions_lock:
        data = _workflow_definitions.get(workflow_id)
    if data:
        logger.debug(f"Found workflow definition {workflow_id}")
    else:
        logger.warning(f"Workflow definition {workflow_id} not found.")
    return data

# --- Utility ---
def clear_all_data():
    """Clears all in-memory data (useful for testing)."""
    logger.warning("Clearing all in-memory storage.")
    with _agent_registrations_lock:
        _agent_registrations.clear()
    with _agent_states_lock:
        _agent_states.clear()
    with _workflow_sessions_lock:
        _workflow_sessions.clear()
    with _workflow_definitions_lock:
        _workflow_definitions.clear()
    logger.info("In-memory storage cleared.")