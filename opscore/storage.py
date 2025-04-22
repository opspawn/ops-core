"""
Ops-Core Storage Subsystem (In-Memory Implementation)

Provides an abstraction layer for persisting and retrieving Ops-Core data,
such as agent registrations, states, sessions, and workflow definitions.

This initial implementation uses simple Python dictionaries for in-memory storage.
It should be replaced with a more robust persistent storage solution (e.g., Redis, DB)
in later phases.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone # Already imported
import threading
import os # Import os to read environment variables
import json # Import json for serialization
import redis.asyncio as redis # Import redis async client


from .models import AgentInfo, AgentState, WorkflowDefinition, WorkflowSession
from . import exceptions # Import custom exceptions
from .logging_config import get_logger

logger = get_logger(__name__)

# --- Storage Implementations ---

class InMemoryStorage:
    """
    In-memory implementation of the Storage subsystem using dictionaries and locks.
    """
    def __init__(self):
        logger.info("Initializing InMemoryStorage")
        # Data Stores
        self._agent_registrations: Dict[str, Dict[str, Any]] = {}
        self._agent_registrations_lock = threading.Lock()
        self._agent_states: Dict[str, List[Dict[str, Any]]] = {} # Store history, latest is last element
        self._agent_states_lock = threading.Lock()
        self._sessions: Dict[str, WorkflowSession] = {}
        self._sessions_lock = threading.Lock()
        self._workflow_definitions: Dict[str, Dict[str, Any]] = {}
        self._workflow_definitions_lock = threading.Lock()

    # --- Agent Registration ---

    def save_agent_registration(self, agent_info: AgentInfo):
        """Saves agent registration details."""
        agent_id = agent_info.agentId
        logger.debug(f"InMemoryStorage: Saving registration for agent {agent_id}")
        try:
            with self._agent_registrations_lock:
                # Store as dict for simplicity in this in-memory version
                self._agent_registrations[agent_id] = agent_info.model_dump(mode='json')
                logger.info(f"InMemoryStorage: Registration saved for agent {agent_id}")
        except (TypeError, ValueError) as e: # Catch specific data errors outside lock if model_dump fails, though unlikely
            logger.error(f"InMemoryStorage: Data error preparing agent registration for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save registration for agent {agent_id} due to data issue", original_exception=e) from e
        except Exception as e: # Catch lock errors or other unexpected issues
            logger.error(f"InMemoryStorage: Unexpected error saving registration for agent {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save registration for agent {agent_id}", original_exception=e) from e

    def read_agent_registration(self, agent_id: str) -> Optional[AgentInfo]:
        """Retrieves agent registration details."""
        logger.debug(f"InMemoryStorage: Retrieving registration for agent {agent_id}")
        with self._agent_registrations_lock:
            data_dict = self._agent_registrations.get(agent_id)
        if data_dict:
            logger.debug(f"InMemoryStorage: Found registration for agent {agent_id}")
            try:
                return AgentInfo(**data_dict)
            except Exception as e: # Handle potential Pydantic validation errors
                 logger.error(f"InMemoryStorage: Failed to parse stored registration data for agent {agent_id}: {e}")
                 return None
        else:
            logger.warning(f"InMemoryStorage: No registration found for agent {agent_id}")
            return None

    def agent_exists(self, agent_id: str) -> bool:
        """Checks if an agent registration exists."""
        with self._agent_registrations_lock:
            exists = agent_id in self._agent_registrations
        logger.debug(f"InMemoryStorage: Checking existence for agent {agent_id}: {exists}")
        return exists

    def get_all_agent_registrations(self) -> List[AgentInfo]:
        """Retrieves all agent registration details."""
        logger.debug("InMemoryStorage: Retrieving all agent registrations")
        agents = []
        with self._agent_registrations_lock:
            agent_dicts = list(self._agent_registrations.values())

        for data_dict in agent_dicts:
            try:
                agents.append(AgentInfo(**data_dict))
            except Exception as e:
                agent_id = data_dict.get('agentId', 'UNKNOWN')
                logger.error(f"InMemoryStorage: Failed to parse stored registration data for agent {agent_id}: {e}")
                # Optionally skip corrupted entries or handle differently

        logger.debug(f"InMemoryStorage: Found {len(agents)} valid agent registrations.")
        return agents

    # --- Agent State ---

    def save_agent_state(self, agent_state: AgentState):
        """Saves an agent state update (appends to history)."""
        agent_id = agent_state.agentId
        logger.debug(f"InMemoryStorage: Saving state for agent {agent_id}: {agent_state.state}")
        try:
            logger.debug(f"InMemoryStorage: Attempting to acquire _agent_states_lock for save_agent_state for agent {agent_id}")
            with self._agent_states_lock:
                logger.debug(f"InMemoryStorage: Acquired _agent_states_lock for save_agent_state for agent {agent_id}")
                if agent_id not in self._agent_states:
                    self._agent_states[agent_id] = []
                # Store as dict for simplicity in this in-memory version
                self._agent_states[agent_id].append(agent_state.model_dump(mode='json'))
                # Optional: Limit history size if needed
                # MAX_HISTORY = 100
                # if len(self._agent_states[agent_id]) > MAX_HISTORY:
                #     logger.debug(f"InMemoryStorage: Trimming state history for agent {agent_id}")
                #     self._agent_states[agent_id] = self._agent_states[agent_id][-MAX_HISTORY:]
                logger.info(f"InMemoryStorage: State saved for agent {agent_id}")
                logger.debug(f"InMemoryStorage: Releasing _agent_states_lock for save_agent_state for agent {agent_id}")
        except (TypeError, ValueError) as e: # Catch specific data errors (e.g., model_dump)
            logger.error(f"InMemoryStorage: Data error during agent state save for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save state for agent {agent_id} due to data issue", original_exception=e) from e
        except Exception as e: # Catch lock errors or other unexpected issues
            logger.error(f"InMemoryStorage: Unexpected error saving state for agent {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save state for agent {agent_id}", original_exception=e) from e
        logger.debug(f"InMemoryStorage: Finished save_agent_state for agent {agent_id}")


    def read_latest_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """Retrieves the most recent state for an agent."""
        logger.debug(f"InMemoryStorage: Retrieving latest state for agent {agent_id}")
        logger.debug(f"InMemoryStorage: Attempting to acquire _agent_states_lock for read_latest_agent_state for agent {agent_id}")
        with self._agent_states_lock:
            logger.debug(f"InMemoryStorage: Acquired _agent_states_lock for read_latest_agent_state for agent {agent_id}")
            history = self._agent_states.get(agent_id)
            if history:
                latest_state_dict = history[-1]
                logger.debug(f"InMemoryStorage: Found latest state dict for agent {agent_id}")
                try:
                    agent_state = AgentState(**latest_state_dict)
                    logger.debug(f"InMemoryStorage: Successfully parsed state data for agent {agent_id}")
                    logger.debug(f"InMemoryStorage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
                    return agent_state
                except Exception as e:
                    logger.error(f"InMemoryStorage: Failed to parse stored state data for agent {agent_id}: {e}")
                    logger.debug(f"InMemoryStorage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
                    return None
            else:
                logger.warning(f"InMemoryStorage: No state history found for agent {agent_id}")
                logger.debug(f"InMemoryStorage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
                return None
        # Lock is released automatically upon exiting the 'with' block
        # logger.debug(f"InMemoryStorage: Finished read_latest_agent_state for agent {agent_id}") # This line is unreachable

    def read_agent_state_history(self, agent_id: str) -> List[AgentState]:
        """Retrieves the full state history for an agent."""
        logger.debug(f"InMemoryStorage: Retrieving state history for agent {agent_id}")
        states = []
        with self._agent_states_lock:
            # Get a copy of the list of dicts
            history_dicts = list(self._agent_states.get(agent_id, []))

        for state_dict in history_dicts:
            try:
                states.append(AgentState(**state_dict))
            except Exception as e:
                logger.error(f"InMemoryStorage: Failed to parse stored state data for agent {agent_id} in history: {e}")
                # Optionally skip corrupted entries

        logger.debug(f"InMemoryStorage: Found {len(states)} valid state entries for agent {agent_id}")
        return states

    # --- Workflow Session ---

    def create_session(self, session: WorkflowSession) -> None:
        """Creates and saves a new workflow session."""
        session_id = session.sessionId
        logger.debug(f"InMemoryStorage: Attempting to create session {session_id}")
        try:
            with self._sessions_lock:
                if session_id in self._sessions:
                    logger.error(f"InMemoryStorage: Session creation failed: Session ID {session_id} already exists.")
                    # Raise a specific storage error for duplicate keys
                    raise exceptions.StorageError(f"Session ID {session_id} already exists.")
                # Store the model directly
                self._sessions[session_id] = session
                logger.info(f"InMemoryStorage: Session {session_id} created successfully.")
        except (TypeError, ValueError) as e: # Catch specific data errors (less likely here)
            logger.error(f"InMemoryStorage: Data error during session creation for {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to create session {session_id} due to data issue", original_exception=e) from e
        except Exception as e: # Catch lock errors or other unexpected issues
            logger.error(f"InMemoryStorage: Unexpected error creating session {session_id}: {e}", exc_info=True)
            # Check if it's the duplicate key StorageError we already raised inside the 'with'
            if isinstance(e, exceptions.StorageError) and "already exists" in str(e):
                 raise e # Re-raise the specific duplicate key error
            # Otherwise, wrap other exceptions as a general StorageError
            raise exceptions.StorageError(f"Failed to create session {session_id}", original_exception=e) from e

    def read_session(self, session_id: str) -> Optional[WorkflowSession]:
        """Retrieves workflow session data by ID."""
        logger.debug(f"InMemoryStorage: Retrieving session {session_id}")
        with self._sessions_lock:
            # Return a copy to prevent external modification? For models, maybe not necessary
            # unless internal state can be mutated. Pydantic models are generally immutable-like.
            session = self._sessions.get(session_id)
        if session:
            logger.debug(f"InMemoryStorage: Found session {session_id}")
        else:
            logger.warning(f"InMemoryStorage: Session {session_id} not found.")
        return session

    def update_session_data(self, session_id: str, update_data: Dict[str, Any]) -> WorkflowSession:
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
        logger.debug(f"InMemoryStorage: Attempting to update session {session_id} with data: {update_data}")
        try:
            with self._sessions_lock:
                if session_id not in self._sessions:
                    logger.error(f"InMemoryStorage: Update failed: Session {session_id} not found.")
                    raise exceptions.SessionNotFoundError(session_id)

                existing_session = self._sessions[session_id]

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
                    self._sessions[session_id] = updated_session # Replace the old session object
                    logger.info(f"InMemoryStorage: Session {session_id} updated successfully.")
                    return updated_session
                except ValueError as e: # Catch Pydantic validation errors specifically
                    logger.error(f"InMemoryStorage: Failed to update session {session_id} due to invalid data: {e}", exc_info=True)
                    # Re-raise the specific InvalidStateError caught from Pydantic validation
                    raise exceptions.InvalidStateError(f"Invalid update data for session {session_id}: {e}") from e
                # No need for broad except Exception here, as it's caught outside the 'with' block

        except Exception as e: # Catch lock errors or other unexpected issues during the update process
            logger.error(f"InMemoryStorage: Unexpected error updating session {session_id}: {e}", exc_info=True)
            # Avoid wrapping SessionNotFoundError or InvalidStateError again
            if not isinstance(e, (exceptions.SessionNotFoundError, exceptions.InvalidStateError)):
                raise exceptions.StorageError(f"Failed to update session {session_id}", original_exception=e) from e
            else:
                raise e # Re-raise the specific caught exceptions

    def delete_session(self, session_id: str) -> bool:
        """Deletes a workflow session by ID."""
        logger.debug(f"InMemoryStorage: Attempting to delete session {session_id}")
        with self._sessions_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"InMemoryStorage: Session {session_id} deleted successfully.")
                return True
            else:
                logger.warning(f"InMemoryStorage: Delete failed: Session {session_id} not found.")
                return False

    # --- Workflow Definition ---

    def save_workflow_definition(self, definition: WorkflowDefinition):
        """Saves a workflow definition."""
        workflow_id = definition.id
        logger.debug(f"InMemoryStorage: Saving workflow definition {workflow_id}")
        try:
            with self._workflow_definitions_lock:
                # Store as dict
                self._workflow_definitions[workflow_id] = definition.model_dump(mode='json')
                logger.info(f"InMemoryStorage: Workflow definition {workflow_id} saved.")
        except (TypeError, ValueError) as e: # Catch specific data errors (e.g., model_dump)
            logger.error(f"InMemoryStorage: Data error saving workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id} due to data issue", original_exception=e) from e
        except Exception as e: # Catch lock errors or other unexpected issues
            logger.error(f"InMemoryStorage: Unexpected error saving workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id}", original_exception=e) from e

    def read_workflow_definition(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Retrieves a workflow definition."""
        logger.debug(f"InMemoryStorage: Retrieving workflow definition {workflow_id}")
        with self._workflow_definitions_lock:
            data_dict = self._workflow_definitions.get(workflow_id)
        if data_dict:
            logger.debug(f"InMemoryStorage: Found workflow definition {workflow_id}")
            try:
                return WorkflowDefinition(**data_dict)
            except Exception as e:
                logger.error(f"InMemoryStorage: Failed to parse stored workflow definition {workflow_id}: {e}")
                return None
        else:
            logger.warning(f"InMemoryStorage: Workflow definition {workflow_id} not found.")
            return None

    # --- Utility ---
    def clear_all_data(self):
        """Clears all in-memory data (useful for testing)."""
        logger.warning("InMemoryStorage: Clearing all in-memory storage.")
        with self._agent_registrations_lock:
            self._agent_registrations.clear()
        with self._agent_states_lock:
            self._agent_states.clear()
        with self._sessions_lock:
            self._sessions.clear()
        with self._workflow_definitions_lock:
            self._workflow_definitions.clear()
        logger.info("InMemoryStorage: In-memory storage cleared.")


# --- Redis Storage Implementation ---

class RedisStorage:
    """
    Redis implementation of the Storage subsystem.
    Uses redis-py async client.
    """
    def __init__(self, host: str = 'localhost', port: int = 6379):
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        logger.info(f"Initialized RedisStorage connected to {host}:{port}")

    async def save_agent_registration(self, agent_info: AgentInfo):
        """Saves agent registration details to Redis."""
        agent_id = agent_info.agentId
        key = f"agent:{agent_id}:registration"
        logger.debug(f"RedisStorage: Saving registration for agent {agent_id} at key {key}")
        try:
            data_json = agent_info.model_dump_json()
            await self.redis_client.set(key, data_json)
            logger.info(f"RedisStorage: Registration saved for agent {agent_id}")
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error saving registration for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save registration for agent {agent_id} to Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error saving registration for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save registration for agent {agent_id} to Redis", original_exception=e) from e

    async def read_agent_registration(self, agent_id: str) -> Optional[AgentInfo]:
        """Retrieves agent registration details from Redis."""
        key = f"agent:{agent_id}:registration"
        logger.debug(f"RedisStorage: Retrieving registration for agent {agent_id} from key {key}")
        try:
            data_json = await self.redis_client.get(key)
            if data_json:
                logger.debug(f"RedisStorage: Found registration for agent {agent_id}")
                try:
                    return AgentInfo.model_validate_json(data_json)
                except Exception as e: # Handle potential Pydantic validation errors
                     logger.error(f"RedisStorage: Failed to parse stored registration data for agent {agent_id}: {e}")
                     return None
            else:
                logger.warning(f"RedisStorage: No registration found for agent {agent_id}")
                return None
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error reading registration for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read registration for agent {agent_id} from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error reading registration for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read registration for agent {agent_id} from Redis", original_exception=e) from e

    async def agent_exists(self, agent_id: str) -> bool:
        """Checks if an agent registration exists in Redis."""
        key = f"agent:{agent_id}:registration"
        logger.debug(f"RedisStorage: Checking existence for agent {agent_id} at key {key}")
        try:
            exists = await self.redis_client.exists(key) > 0
            logger.debug(f"RedisStorage: Existence check for agent {agent_id}: {exists}")
            return exists
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error checking existence for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to check existence for agent {agent_id} in Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error checking existence for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to check existence for agent {agent_id} in Redis", original_exception=e) from e

    async def get_all_agent_registrations(self) -> List[AgentInfo]:
        """Retrieves all agent registration details from Redis."""
        logger.debug("RedisStorage: Retrieving all agent registrations")
        agents: List[AgentInfo] = []
        try:
            # Scan for all registration keys
            keys = []
            async for key in self.redis_client.scan_iter("agent:*:registration"):
                keys.append(key)

            if not keys:
                logger.debug("RedisStorage: No agent registration keys found.")
                return []

            # Use MGET to retrieve all values efficiently
            data_jsons = await self.redis_client.mget(keys)

            for data_json in data_jsons:
                if data_json:
                    try:
                        agents.append(AgentInfo.model_validate_json(data_json))
                    except Exception as e:
                        # Attempt to get agent_id from key if possible, or from data_json if parsed partially
                        agent_id = "UNKNOWN"
                        try:
                            # Extract agent_id from key format "agent:{agent_id}:registration"
                            key_str = keys[data_jsons.index(data_json)]
                            parts = key_str.split(':')
                            if len(parts) > 1:
                                agent_id = parts[1]
                        except Exception:
                            pass # Ignore errors during key parsing

                        logger.error(f"RedisStorage: Failed to parse stored registration data for agent {agent_id}: {e}")
                        # Optionally skip corrupted entries or handle differently

            logger.debug(f"RedisStorage: Found {len(agents)} valid agent registrations.")
            return agents
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error retrieving all registrations: {e}", exc_info=True)
            raise exceptions.StorageError("Failed to retrieve all agent registrations from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error retrieving all registrations: {e}", exc_info=True)
            raise exceptions.StorageError("Failed to retrieve all agent registrations from Redis", original_exception=e) from e


    # --- Agent State ---

:start_line:445
-------
    async def save_agent_state(self, agent_state: AgentState):
        """Saves an agent state update to Redis (stores latest state)."""
        agent_id = agent_state.agentId
        key = f"agent:{agent_id}:latest_state"
        logger.debug(f"RedisStorage: Entering save_agent_state for agent {agent_id}")
        logger.debug(f"RedisStorage: Saving state for agent {agent_id}: {agent_state.state} at key {key}")
        try:
            data_json = agent_state.model_dump_json()
            await self.redis_client.set(key, data_json)
            logger.info(f"RedisStorage: State saved for agent {agent_id}")
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error saving state for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save state for agent {agent_id} to Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error saving state for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save state for agent {agent_id} to Redis", original_exception=e) from e
        logger.debug(f"RedisStorage: Exiting save_agent_state for agent {agent_id}")

    async def read_latest_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """Retrieves the most recent state for an agent from Redis."""
        key = f"agent:{agent_id}:latest_state"
        logger.debug(f"RedisStorage: Retrieving latest state for agent {agent_id} from key {key}")
        try:
            data_json = await self.redis_client.get(key)
            if data_json:
                logger.debug(f"RedisStorage: Found latest state data for agent {agent_id}")
                try:
                    return AgentState.model_validate_json(data_json)
                except Exception as e:
                    logger.error(f"RedisStorage: Failed to parse stored state data for agent {agent_id}: {e}")
                    return None
            else:
                logger.warning(f"RedisStorage: No latest state found for agent {agent_id}")
                return None
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error reading latest state for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read latest state for agent {agent_id} from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error reading latest state for {agent_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read latest state for agent {agent_id} from Redis", original_exception=e) from e

    async def read_agent_state_history(self, agent_id: str) -> List[AgentState]:
        """
        Retrieves the full state history for an agent from Redis.
        (Note: This implementation only stores the latest state. History would require a different Redis structure like a List or Sorted Set.)
        For now, return a list containing only the latest state if found.
        """
        logger.debug(f"RedisStorage: Retrieving state history for agent {agent_id}")
        latest_state = await self.read_latest_agent_state(agent_id)
        if latest_state:
            logger.debug(f"RedisStorage: Returning latest state as history for agent {agent_id}")
            return [latest_state]
        else:
            logger.debug(f"RedisStorage: No state history found for agent {agent_id}")
            return []

    # --- Workflow Session ---

    async def create_session(self, session: WorkflowSession) -> None:
        """Creates and saves a new workflow session to Redis."""
        session_id = session.sessionId
        key = f"session:{session_id}"
        logger.debug(f"RedisStorage: Attempting to create session {session_id} at key {key}")
        try:
            data_json = session.model_dump_json()
            # Use SET with NX (Not Exists) to ensure it's a create operation
            set_result = await self.redis_client.set(key, data_json, nx=True)
            if set_result is True: # SET with NX returns True on success, None if key exists
                logger.info(f"RedisStorage: Session {session_id} created successfully.")
            else:
                logger.error(f"RedisStorage: Session creation failed: Session ID {session_id} already exists.")
                raise exceptions.StorageError(f"Session ID {session_id} already exists.")
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error creating session {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to create session {session_id} in Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error creating session {session_id}: {e}", exc_info=True)
            if not isinstance(e, exceptions.StorageError): # Avoid wrapping our own raised error
                 raise exceptions.StorageError(f"Failed to create session {session_id} in Redis", original_exception=e) from e
            else:
                 raise e # Re-raise the specific caught exceptions


    async def read_session(self, session_id: str) -> Optional[WorkflowSession]:
        """Retrieves workflow session data by ID from Redis."""
        key = f"session:{session_id}"
        logger.debug(f"RedisStorage: Retrieving session {session_id} from key {key}")
        try:
            data_json = await self.redis_client.get(key)
            if data_json:
                logger.debug(f"RedisStorage: Found session {session_id}")
                try:
                    return WorkflowSession.model_validate_json(data_json)
                except Exception as e:
                    logger.error(f"RedisStorage: Failed to parse stored session data for {session_id}: {e}")
                    return None
            else:
                logger.warning(f"RedisStorage: Session {session_id} not found.")
                return None
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error reading session {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read session {session_id} from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error reading session {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read session {session_id} from Redis", original_exception=e) from e

    async def update_session_data(self, session_id: str, update_data: Dict[str, Any]) -> WorkflowSession:
        """
        Updates specific fields of an existing workflow session in Redis.
        Reads the existing session, updates the dictionary, re-validates with Pydantic,
        and saves the updated session back to Redis.
        """
        key = f"session:{session_id}"
        logger.debug(f"RedisStorage: Attempting to update session {session_id} at key {key} with data: {update_data}")
        try:
            # Read existing session
            existing_session = await self.read_session(session_id)
            if not existing_session:
                logger.error(f"RedisStorage: Update failed: Session {session_id} not found.")
                raise exceptions.SessionNotFoundError(session_id)

            # Update data dictionary
            updated_session_data = existing_session.model_dump()
            updated_session_data.update(update_data)
            # Ensure last_updated_time is always set by the caller or here
            if 'last_updated_time' not in update_data:
                 updated_session_data['last_updated_time'] = datetime.now(timezone.utc) # Use timezone-aware

            # Re-validate and save
            try:
                updated_session = WorkflowSession(**updated_session_data)
                data_json = updated_session.model_dump_json()
                await self.redis_client.set(key, data_json) # SET will overwrite if key exists
                logger.info(f"RedisStorage: Session {session_id} updated successfully.")
                return updated_session
            except ValueError as e: # Catch Pydantic validation errors specifically
                logger.error(f"RedisStorage: Failed to update session {session_id} due to invalid data: {e}", exc_info=True)
                raise exceptions.InvalidStateError(f"Invalid update data for session {session_id}: {e}") from e

        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error updating session {session_id}: {e}", exc_info=True)
            # Avoid wrapping SessionNotFoundError or InvalidStateError again
            if not isinstance(e, (exceptions.SessionNotFoundError, exceptions.InvalidStateError)):
                raise exceptions.StorageError(f"Failed to update session {session_id} in Redis", original_exception=e) from e
            else:
                raise e # Re-raise the specific caught exceptions
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error updating session {session_id}: {e}", exc_info=True)
            if not isinstance(e, (exceptions.SessionNotFoundError, exceptions.InvalidStateError)):
                raise exceptions.StorageError(f"Failed to update session {session_id} in Redis", original_exception=e) from e
            else:
                raise e # Re-raise the specific caught exceptions


    async def delete_session(self, session_id: str) -> bool:
        """Deletes a workflow session by ID from Redis."""
        key = f"session:{session_id}"
        logger.debug(f"RedisStorage: Attempting to delete session {session_id} at key {key}")
        try:
            # DEL command returns the number of keys removed
            deleted_count = await self.redis_client.delete(key)
            if deleted_count > 0:
                logger.info(f"RedisStorage: Session {session_id} deleted successfully.")
                return True
            else:
                logger.warning(f"RedisStorage: Delete failed: Session {session_id} not found.")
                return False
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error deleting session {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to delete session {session_id} from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error deleting session {session_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to delete session {session_id} from Redis", original_exception=e) from e

    # --- Workflow Definition ---

    async def save_workflow_definition(self, definition: WorkflowDefinition):
        """Saves a workflow definition to Redis."""
        workflow_id = definition.id
        key = f"workflow_def:{workflow_id}"
        logger.debug(f"RedisStorage: Saving workflow definition {workflow_id} at key {key}")
        try:
            data_json = definition.model_dump_json()
            await self.redis_client.set(key, data_json)
            logger.info(f"RedisStorage: Workflow definition {workflow_id} saved.")
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error saving workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id} to Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error saving workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to save workflow definition {workflow_id} to Redis", original_exception=e) from e

    async def read_workflow_definition(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Retrieves a workflow definition from Redis."""
        key = f"workflow_def:{workflow_id}"
        logger.debug(f"RedisStorage: Retrieving workflow definition {workflow_id} from key {key}")
        try:
            data_json = await self.redis_client.get(key)
            if data_json:
                logger.debug(f"RedisStorage: Found workflow definition {workflow_id}")
                try:
                    return WorkflowDefinition.model_validate_json(data_json)
                except Exception as e:
                    logger.error(f"RedisStorage: Failed to parse stored workflow definition {workflow_id}: {e}")
                    return None
            else:
                logger.warning(f"RedisStorage: Workflow definition {workflow_id} not found.")
                return None
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error reading workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read workflow definition {workflow_id} from Redis", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error reading workflow definition {workflow_id}: {e}", exc_info=True)
            raise exceptions.StorageError(f"Failed to read workflow definition {workflow_id} from Redis", original_exception=e) from e

    # --- Utility ---
    async def clear_all_data(self):
        """Clears all data in the connected Redis database."""
        logger.warning("RedisStorage: Clearing all data in Redis database.")
        try:
            await self.redis_client.flushdb()
            logger.info("RedisStorage: Redis database cleared.")
        except redis.RedisError as e:
            logger.error(f"RedisStorage: Redis error clearing database: {e}", exc_info=True)
            raise exceptions.StorageError("Failed to clear Redis database", original_exception=e) from e
        except Exception as e:
            logger.error(f"RedisStorage: Unexpected error clearing database: {e}", exc_info=True)
            raise exceptions.StorageError("Failed to clear Redis database", original_exception=e) from e

# --- Storage Selection Logic ---

# Module-level variable to hold the active storage instance
_active_storage: Optional[Union[InMemoryStorage, RedisStorage]] = None

def get_storage() -> Union[InMemoryStorage, RedisStorage]:
    """
    Returns the active storage instance based on environment configuration.
    Initializes the storage instance on the first call.
    """
    global _active_storage
    if _active_storage is None:
        storage_type = os.environ.get("OPSCORE_STORAGE_TYPE", "inmemory").lower()
        if storage_type == "redis":
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            _active_storage = RedisStorage(host=redis_host, port=redis_port)
        else:
            _active_storage = InMemoryStorage()
            logger.info("Initialized InMemoryStorage")
    return _active_storage

# Replace direct usage of in-memory functions with calls to the active storage instance
# This requires refactoring the functions below to use the instance methods.

# Deprecated functions removed.


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
    logger.debug(f"Storage: Saving state for agent {agent_id}: {agent_state.state}")
    try:
        logger.debug(f"Storage: Attempting to acquire _agent_states_lock for save_agent_state for agent {agent_id}")
        with _agent_states_lock:
            logger.debug(f"Storage: Acquired _agent_states_lock for save_agent_state for agent {agent_id}")
            if agent_id not in _agent_states:
                _agent_states[agent_id] = []
            # Store as dict for simplicity in this in-memory version
            _agent_states[agent_id].append(agent_state.model_dump(mode='json'))
            # Optional: Limit history size if needed
            # MAX_HISTORY = 100
            # if len(_agent_states[agent_id]) > MAX_HISTORY:
            #     logger.debug(f"Storage: Trimming state history for agent {agent_id}")
            #     _agent_states[agent_id] = _agent_states[agent_id][-MAX_HISTORY:]
            logger.info(f"Storage: State saved for agent {agent_id}")
            logger.debug(f"Storage: Releasing _agent_states_lock for save_agent_state for agent {agent_id}")
    except (TypeError, ValueError) as e: # Catch specific data errors (e.g., model_dump)
        logger.error(f"Storage: Data error during agent state save for {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id} due to data issue", original_exception=e) from e
    except Exception as e: # Catch lock errors or other unexpected issues
        logger.error(f"Storage: Unexpected error saving state for agent {agent_id}: {e}", exc_info=True)
        raise exceptions.StorageError(f"Failed to save state for agent {agent_id}", original_exception=e) from e
    logger.debug(f"Storage: Finished save_agent_state for agent {agent_id}")


def read_latest_agent_state(agent_id: str) -> Optional[AgentState]:
    """Retrieves the most recent state for an agent."""
    logger.debug(f"Storage: Retrieving latest state for agent {agent_id}")
    logger.debug(f"Storage: Attempting to acquire _agent_states_lock for read_latest_agent_state for agent {agent_id}")
    with _agent_states_lock:
        logger.debug(f"Storage: Acquired _agent_states_lock for read_latest_agent_state for agent {agent_id}")
        history = _agent_states.get(agent_id)
        if history:
            latest_state_dict = history[-1]
            logger.debug(f"Storage: Found latest state dict for agent {agent_id}")
            try:
                agent_state = AgentState(**latest_state_dict)
                logger.debug(f"Storage: Successfully parsed state data for agent {agent_id}")
                logger.debug(f"Storage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
                return agent_state
            except Exception as e:
                logger.error(f"Storage: Failed to parse stored state data for agent {agent_id}: {e}")
                logger.debug(f"Storage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
                return None
        else:
            logger.warning(f"Storage: No state history found for agent {agent_id}")
            logger.debug(f"Storage: Releasing _agent_states_lock for read_latest_agent_state for agent {agent_id}")
            return None
    # Lock is released automatically upon exiting the 'with' block
    # logger.debug(f"Storage: Finished read_latest_agent_state for agent {agent_id}") # This line is unreachable

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