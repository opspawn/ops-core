"""
Unit tests for the opscore.storage module.
"""

import pytest
from opscore import storage, models, exceptions # Import exceptions
from datetime import datetime, timezone # Import timezone
from unittest.mock import patch # Import patch

# Fixtures from conftest.py are automatically available
# Includes: clear_storage_before_each_test (autouse), valid_agent_info, valid_agent_state,
#           valid_session_model, valid_workflow_def_model

# --- Agent Registration Tests ---

def test_save_read_agent_registration_success(valid_agent_info):
    """Test saving and reading a valid agent registration."""
    agent_id = valid_agent_info.agentId
    storage.save_agent_registration(valid_agent_info)
    retrieved_info = storage.read_agent_registration(agent_id)

    assert retrieved_info is not None
    assert retrieved_info.agentId == agent_id
    assert retrieved_info.agentName == valid_agent_info.agentName
    assert retrieved_info.registrationTime == valid_agent_info.registrationTime
    # Compare model dumps for full equality check if needed
    assert retrieved_info.model_dump() == valid_agent_info.model_dump()

def test_read_agent_registration_not_found():
    """Test reading a non-existent agent registration returns None."""
    retrieved_info = storage.read_agent_registration("non_existent_agent")
    assert retrieved_info is None

def test_agent_exists(valid_agent_info):
    """Test agent_exists function."""
    agent_id = valid_agent_info.agentId
    assert not storage.agent_exists(agent_id) # Should not exist before saving
    storage.save_agent_registration(valid_agent_info)
    assert storage.agent_exists(agent_id) # Should exist after saving
    assert not storage.agent_exists("another_agent") # Check non-existent

def test_get_all_agent_registrations(valid_agent_info):
    """Test retrieving all agent registrations."""
    assert storage.get_all_agent_registrations() == [] # Should be empty initially

    agent_info_1 = valid_agent_info
    agent_info_2 = models.AgentInfo(
        agentId="agent_test_456",
        agentName="SecondAgent",
        version="2.0",
        capabilities=["cap1"],
        contactEndpoint="http://localhost:9001",
        metadata={},
        registrationTime=datetime.now(timezone.utc) # Use timezone-aware
    )

    storage.save_agent_registration(agent_info_1)
    storage.save_agent_registration(agent_info_2)

    all_agents = storage.get_all_agent_registrations()
    assert len(all_agents) == 2
    # Check if both agents are present (order might not be guaranteed)
    agent_ids_retrieved = {agent.agentId for agent in all_agents}
    assert agent_ids_retrieved == {agent_info_1.agentId, agent_info_2.agentId}

# --- Agent State Tests ---

def test_save_read_latest_agent_state_success(valid_agent_state):
    """Test saving and reading the latest agent state."""
    agent_id = valid_agent_state.agentId
    # Need to register agent first for state saving context (though not strictly enforced by storage)
    # storage.save_agent_registration(...) # Optional depending on future constraints

    storage.save_agent_state(valid_agent_state)
    retrieved_state = storage.read_latest_agent_state(agent_id)

    assert retrieved_state is not None
    assert retrieved_state.agentId == agent_id
    assert retrieved_state.state == valid_agent_state.state
    assert retrieved_state.timestamp == valid_agent_state.timestamp
    assert retrieved_state.model_dump() == valid_agent_state.model_dump()

def test_read_latest_agent_state_multiple(valid_agent_state):
    """Test that read_latest_agent_state returns the most recent state."""
    agent_id = valid_agent_state.agentId
    state1 = valid_agent_state
    state2 = models.AgentState(
        agentId=agent_id,
        state="active",
        details={"current_task": "abc"},
        timestamp=datetime.now(timezone.utc) # Later timestamp (timezone-aware)
    )

    storage.save_agent_state(state1)
    storage.save_agent_state(state2)

    latest_state = storage.read_latest_agent_state(agent_id)
    assert latest_state is not None
    assert latest_state.state == "active"
    assert latest_state.timestamp == state2.timestamp

def test_read_latest_agent_state_not_found():
    """Test reading latest state for an agent with no history."""
    retrieved_state = storage.read_latest_agent_state("agent_with_no_state")
    assert retrieved_state is None

def test_read_agent_state_history(valid_agent_state):
    """Test retrieving agent state history."""
    agent_id = valid_agent_state.agentId
    assert storage.read_agent_state_history(agent_id) == [] # Empty initially

    state1 = valid_agent_state
    state2 = models.AgentState(agentId=agent_id, state="active", timestamp=datetime.now(timezone.utc)) # Use timezone-aware
    state3 = models.AgentState(agentId=agent_id, state="finished", timestamp=datetime.now(timezone.utc)) # Use timezone-aware

    storage.save_agent_state(state1)
    storage.save_agent_state(state2)
    storage.save_agent_state(state3)

    history = storage.read_agent_state_history(agent_id)
    assert len(history) == 3
    assert history[0].state == state1.state
    assert history[1].state == state2.state
    assert history[2].state == state3.state
    assert history[0].timestamp == state1.timestamp

# --- Workflow Session Tests ---

def test_create_read_session_success(valid_session_model):
    """Test creating and reading a valid session."""
    session_id = valid_session_model.sessionId
    storage.create_session(valid_session_model)
    retrieved_session = storage.read_session(session_id)

    assert retrieved_session is not None
    assert retrieved_session.sessionId == session_id
    assert retrieved_session.agentId == valid_session_model.agentId
    assert retrieved_session.model_dump() == valid_session_model.model_dump()

def test_create_session_duplicate_id(valid_session_model):
    """Test that creating a session with a duplicate ID raises StorageError."""
    storage.create_session(valid_session_model)
    with pytest.raises(exceptions.StorageError, match=f"Session ID {valid_session_model.sessionId} already exists"):
        storage.create_session(valid_session_model) # Try creating again

def test_read_session_not_found():
    """Test reading a non-existent session returns None."""
    retrieved_session = storage.read_session("non_existent_session")
    assert retrieved_session is None

def test_update_session_data_success(valid_session_model):
    """Test successfully updating session data."""
    session_id = valid_session_model.sessionId
    storage.create_session(valid_session_model)

    update_time = datetime.now(timezone.utc) # Use timezone-aware
    update_data = {
        "status": "running",
        "metadata": {"key": "value"},
        "last_updated_time": update_time
    }
    updated_session = storage.update_session_data(session_id, update_data)

    assert updated_session is not None
    assert updated_session.sessionId == session_id
    assert updated_session.status == "running"
    assert updated_session.metadata == {"key": "value"}
    assert updated_session.last_updated_time == update_time
    # Ensure other fields are preserved
    assert updated_session.agentId == valid_session_model.agentId

    # Verify the update is persisted
    retrieved_session = storage.read_session(session_id)
    assert retrieved_session is not None
    assert retrieved_session.status == "running"
    assert retrieved_session.last_updated_time == update_time

def test_update_session_data_not_found(valid_session_model):
    """Test updating a non-existent session raises SessionNotFoundError."""
    # Match the actual exception message format
    with pytest.raises(exceptions.SessionNotFoundError, match="Session not found: non_existent_session"):
        storage.update_session_data("non_existent_session", {"status": "failed"})

def test_update_session_data_invalid_data(valid_session_model):
    """Test updating with invalid data raises InvalidStateError (from Pydantic)."""
    session_id = valid_session_model.sessionId
    storage.create_session(valid_session_model)
    with pytest.raises(exceptions.InvalidStateError, match="Invalid update data for session"): # Pydantic validation error becomes InvalidStateError
        storage.update_session_data(session_id, {"status": 123}) # Invalid type for status

def test_delete_session(valid_session_model):
    """Test deleting a session."""
    session_id = valid_session_model.sessionId
    storage.create_session(valid_session_model)

    assert storage.read_session(session_id) is not None # Exists before delete
    delete_result = storage.delete_session(session_id)
    assert delete_result is True
    assert storage.read_session(session_id) is None # Does not exist after delete

def test_delete_session_not_found():
    """Test deleting a non-existent session returns False."""
    delete_result = storage.delete_session("non_existent_session")
    assert delete_result is False

# --- Workflow Definition Tests ---

def test_save_read_workflow_definition_success(valid_workflow_def_model):
    """Test saving and reading a valid workflow definition."""
    workflow_id = valid_workflow_def_model.id
    storage.save_workflow_definition(valid_workflow_def_model)
    retrieved_def = storage.read_workflow_definition(workflow_id)

    assert retrieved_def is not None
    assert retrieved_def.id == workflow_id
    assert retrieved_def.name == valid_workflow_def_model.name
    assert retrieved_def.model_dump() == valid_workflow_def_model.model_dump()

def test_read_workflow_definition_not_found():
    """Test reading a non-existent workflow definition returns None."""
    retrieved_def = storage.read_workflow_definition("wf_non_existent")
    assert retrieved_def is None

# --- Utility Tests ---

def test_clear_all_data(valid_agent_info, valid_session_model, valid_workflow_def_model, valid_agent_state):
    """Test that clear_all_data empties all storage."""
    # Populate some data
    storage.save_agent_registration(valid_agent_info)
    storage.save_agent_state(valid_agent_state)
    storage.create_session(valid_session_model)
    storage.save_workflow_definition(valid_workflow_def_model)

    # Verify data exists
    assert storage.agent_exists(valid_agent_info.agentId)
    assert storage.read_latest_agent_state(valid_agent_state.agentId) is not None
    assert storage.read_session(valid_session_model.sessionId) is not None
    assert storage.read_workflow_definition(valid_workflow_def_model.id) is not None

    # Clear data
    storage.clear_all_data()

    # Verify data is cleared
    assert not storage.agent_exists(valid_agent_info.agentId)
    assert storage.read_latest_agent_state(valid_agent_state.agentId) is None
    assert storage.read_session(valid_session_model.sessionId) is None
    assert storage.read_workflow_definition(valid_workflow_def_model.id) is None
    assert storage.get_all_agent_registrations() == []

# --- Storage Error Tests ---

# --- Storage Error Tests (Refactored to avoid lazy_fixture) ---

@patch('opscore.storage.threading.Lock') # Patch Lock class where it's used
def test_save_agent_registration_storage_error(MockLock, valid_agent_info):
    """Test save_agent_registration raises StorageError on underlying exceptions."""
    # Configure the mocked Lock instance's acquire method
    mock_instance = MockLock.return_value
    mock_instance.acquire.side_effect = RuntimeError("Simulated lock error")

    with pytest.raises(exceptions.StorageError, match="Failed to save registration"):
        storage.save_agent_registration(valid_agent_info)
    mock_instance.acquire.assert_called_once() # Verify lock was attempted

@patch('opscore.storage.threading.Lock') # Patch Lock class where it's used
def test_save_agent_state_storage_error(MockLock, valid_agent_state):
    """Test save_agent_state raises StorageError on underlying exceptions."""
    # Configure the mocked Lock instance's acquire method
    mock_instance = MockLock.return_value
    mock_instance.acquire.side_effect = RuntimeError("Simulated lock error")

    # Prerequisite: Ensure agent is registered (bypassing lock for setup)
    # We need a separate patch context here to allow the prerequisite save
    with patch('opscore.storage.threading.Lock') as MockLockSetup:
        mock_setup_instance = MockLockSetup.return_value
        mock_setup_instance.acquire.return_value = True # Simulate successful lock for setup
        mock_setup_instance.release.return_value = True

        minimal_agent_info = models.AgentInfo(
            agentId=valid_agent_state.agentId, agentName="test-prereq", version="1.0", contactEndpoint="http://localhost:1234"
        )
        storage.save_agent_registration(minimal_agent_info)

    # Now test the actual save_agent_state with the failing lock mock active
    with pytest.raises(exceptions.StorageError, match="Failed to save state"):
        storage.save_agent_state(valid_agent_state)
    mock_instance.acquire.assert_called_once() # Verify lock was attempted

@patch('opscore.storage.threading.Lock') # Patch Lock class where it's used
def test_create_session_storage_error(MockLock, valid_session_model):
    """Test create_session raises StorageError on underlying exceptions (not duplicate ID)."""
    # Configure the mocked Lock instance's acquire method
    mock_instance = MockLock.return_value
    mock_instance.acquire.side_effect = RuntimeError("Simulated lock error")

    # Use a unique ID to avoid duplicate key error
    unique_session = valid_session_model.model_copy(update={"sessionId": f"sess_generic_error_test_{datetime.now().isoformat()}"})
    storage._sessions.pop(unique_session.sessionId, None) # Ensure it's clear

    with pytest.raises(exceptions.StorageError, match="Failed to create session"):
        storage.create_session(unique_session)
    mock_instance.acquire.assert_called_once() # Verify lock was attempted

@patch('opscore.storage.threading.Lock') # Patch Lock class where it's used
def test_save_workflow_definition_storage_error(MockLock, valid_workflow_def_model):
    """Test save_workflow_definition raises StorageError on underlying exceptions."""
    # Configure the mocked Lock instance's acquire method
    mock_instance = MockLock.return_value
    mock_instance.acquire.side_effect = RuntimeError("Simulated lock error")

    with pytest.raises(exceptions.StorageError, match="Failed to save workflow definition"):
        storage.save_workflow_definition(valid_workflow_def_model)
    mock_instance.acquire.assert_called_once() # Verify lock was attempted

@patch('opscore.storage.threading.Lock') # Patch Lock class where it's used
def test_update_session_data_storage_error(MockLock, valid_session_model):
    """Test update_session_data raises StorageError on underlying exceptions."""
    # Configure the mocked Lock instance's acquire method
    mock_instance = MockLock.return_value
    mock_instance.acquire.side_effect = RuntimeError("Simulated lock error")

    # Need to successfully create the session first, bypassing the lock mock for setup
    with patch('opscore.storage.threading.Lock') as MockLockSetup:
         mock_setup_instance = MockLockSetup.return_value
         mock_setup_instance.acquire.return_value = True
         mock_setup_instance.release.return_value = True
         storage.create_session(valid_session_model)

    # Now test the update with the lock failing
    update_data = {"status": "failed", "last_updated_time": datetime.now(timezone.utc)}
    with pytest.raises(exceptions.StorageError, match="Failed to update session"):
        storage.update_session_data(valid_session_model.sessionId, update_data)
    mock_instance.acquire.assert_called_once() # Verify lock was attempted