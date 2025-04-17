"""
Unit tests for the opscore.lifecycle module.
"""

import pytest
import uuid # Add missing import
from opscore import lifecycle, storage, models
from datetime import datetime, timezone # Import timezone

# Fixtures from conftest.py are automatically available
# Includes: clear_storage_before_each_test (autouse), valid_agent_reg_details,
#           valid_agent_info, valid_agent_state, valid_session_model

# --- Agent Registration Tests ---

def test_register_agent_success(valid_agent_reg_details):
    """Test successful agent registration."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details)

    assert isinstance(agent_info, models.AgentInfo)
    assert agent_info.agentId.startswith("agent_")
    assert agent_info.agentName == valid_agent_reg_details.agentName

    # Verify it was saved in storage
    retrieved_agent = storage.read_agent_registration(agent_info.agentId)
    assert retrieved_agent is not None
    assert retrieved_agent.agentId == agent_info.agentId
    assert retrieved_agent.agentName == agent_info.agentName

def test_register_agent_invalid_details():
    """Test agent registration with invalid details raises ValueError."""
    invalid_details_dict = {
        "agentName": "InvalidAgent",
        # Missing required fields like version, contactEndpoint
    }
    # Create the model instance to trigger Pydantic validation *before* calling register_agent
    with pytest.raises(ValueError): # Pydantic raises ValidationError, caught as ValueError
         models.AgentRegistrationDetails(**invalid_details_dict)

    # If we were passing dict directly to register_agent, the test would be:
    # with pytest.raises(ValueError, match="Invalid agent registration details"):
    #     lifecycle.register_agent(invalid_details_dict)


# --- State Management Tests ---

def test_set_state_success(valid_agent_reg_details): # Use correct fixture
    """Test setting state for a registered agent."""
    # Register agent first
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID

    new_state = "active"
    details = {"task": "processing data"}
    timestamp_str = datetime.now(timezone.utc).isoformat() # Use timezone-aware

    lifecycle.set_state(agent_id, new_state, details, timestamp_str)

    # Verify state saved in storage
    retrieved_state = storage.read_latest_agent_state(agent_id)
    assert retrieved_state is not None
    assert retrieved_state.agentId == agent_id
    assert retrieved_state.state == new_state
    assert retrieved_state.details == details
    # Timestamps might have slight precision differences, compare reasonably
    assert abs((retrieved_state.timestamp - datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))).total_seconds()) < 1

def test_set_state_agent_not_found():
    """Test setting state for an unknown agent raises ValueError."""
    with pytest.raises(ValueError, match="Agent not found: unknown_agent"):
        lifecycle.set_state("unknown_agent", "idle")

def test_set_state_invalid_timestamp(valid_agent_reg_details): # Use correct fixture
    """Test setting state with an invalid timestamp format (should log warning and use current time)."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID

    # No exception should be raised, but a warning logged (can't easily test logs here without caplog)
    lifecycle.set_state(agent_id, "error", timestamp="invalid-time-format")

    retrieved_state = storage.read_latest_agent_state(agent_id)
    assert retrieved_state is not None
    assert retrieved_state.state == "error"
    # Verify timestamp is recent (close to now) - use timezone-aware if possible
    # Use timezone.utc for compatibility
    assert abs((datetime.now(timezone.utc) - retrieved_state.timestamp.replace(tzinfo=timezone.utc)).total_seconds()) < 5 # Within 5 seconds

def test_get_state_success(valid_agent_reg_details): # Use correct fixture
    """Test getting state for an agent with state history."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    lifecycle.set_state(agent_id, "idle")
    lifecycle.set_state(agent_id, "active", details={"task": "xyz"})

    retrieved_state = lifecycle.get_state(agent_id)
    assert isinstance(retrieved_state, models.AgentState)
    assert retrieved_state.state == "active"
    assert retrieved_state.details == {"task": "xyz"}

def test_get_state_not_found(valid_agent_reg_details): # Use correct fixture
    """Test getting state for a registered agent with no state history."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    retrieved_state = lifecycle.get_state(agent_id)
    assert retrieved_state is None

def test_get_state_agent_not_registered():
    """Test getting state for an agent that was never registered."""
    # Note: get_state itself doesn't check registration, relies on storage returning None
    retrieved_state = lifecycle.get_state("never_registered_agent")
    assert retrieved_state is None

# --- Session Management Tests ---

def test_start_session_success(valid_agent_reg_details): # Use correct fixture
    """Test starting a new session successfully."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    workflow_id = "wf_test_start"

    session = lifecycle.start_session(agent_id, workflow_id)

    assert isinstance(session, models.WorkflowSession)
    assert session.agentId == agent_id
    assert session.workflowId == workflow_id
    assert session.status == "started"
    # Check if sessionId is a valid UUID string (default factory)
    try:
        uuid.UUID(session.sessionId)
        is_uuid = True
    except ValueError:
        is_uuid = False
    assert is_uuid

    # Verify saved in storage
    retrieved_session = storage.read_session(session.sessionId)
    assert retrieved_session is not None
    assert retrieved_session.sessionId == session.sessionId
    assert retrieved_session.agentId == agent_id

def test_start_session_agent_not_found():
    """Test starting a session for an unknown agent raises ValueError."""
    with pytest.raises(ValueError, match="Agent not found: unknown_agent"):
        lifecycle.start_session("unknown_agent", "wf_test_start")

def test_update_session_success(valid_agent_reg_details): # Use correct fixture
    """Test updating an existing session."""
    # Setup: Register agent and start a session
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    workflow_id = "wf_update_test" # Use a specific workflow ID
    initial_session = lifecycle.start_session(agent_id, workflow_id)
    session_id = initial_session.sessionId

    update_payload = models.SessionUpdate(
        status="running",
        metadata={"progress": 50}
    )
    updated_session = lifecycle.update_session(session_id, update_payload)

    assert isinstance(updated_session, models.WorkflowSession)
    assert updated_session.sessionId == session_id
    assert updated_session.status == "running"
    assert updated_session.metadata == {"progress": 50}
    assert updated_session.last_updated_time > initial_session.last_updated_time

    # Verify update persisted
    retrieved_session = storage.read_session(session_id)
    assert retrieved_session is not None
    assert retrieved_session.status == "running"
    assert retrieved_session.metadata == {"progress": 50}

def test_update_session_terminal_state_sets_endtime(valid_agent_reg_details): # Use correct fixture
    """Test that updating to a terminal status sets the endTime."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    session = lifecycle.start_session(agent_id, "wf_term_test")

    assert session.endTime is None # Should be None initially

    update_payload = models.SessionUpdate(status="completed", result={"output": "done"})
    updated_session = lifecycle.update_session(session.sessionId, update_payload)

    assert updated_session.status == "completed"
    assert updated_session.endTime is not None
    # Use timezone.utc for compatibility
    assert abs((datetime.now(timezone.utc) - updated_session.endTime.replace(tzinfo=timezone.utc)).total_seconds()) < 5 # End time is recent

    # Verify persisted
    retrieved = storage.read_session(session.sessionId)
    assert retrieved.endTime is not None

def test_update_session_not_found():
    """Test updating a non-existent session raises ValueError."""
    update_payload = models.SessionUpdate(status="failed")
    with pytest.raises(ValueError, match="Session not found: non_existent_session"):
        lifecycle.update_session("non_existent_session", update_payload)

def test_update_session_empty_payload(valid_agent_reg_details): # Use correct fixture
    """Test updating with an empty payload doesn't change the session (and doesn't error)."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    initial_session = lifecycle.start_session(agent_id, "wf_empty_update")
    initial_dump = initial_session.model_dump()

    update_payload = models.SessionUpdate() # No fields set
    updated_session = lifecycle.update_session(initial_session.sessionId, update_payload)

    # Should return the same session data, potentially different object instance
    assert updated_session.model_dump() == initial_dump

    # Verify no change in storage
    retrieved_session = storage.read_session(initial_session.sessionId)
    assert retrieved_session.model_dump() == initial_dump


def test_get_session_success(valid_agent_reg_details): # Use correct fixture
    """Test getting an existing session."""
    agent_info = lifecycle.register_agent(valid_agent_reg_details) # Capture returned AgentInfo
    agent_id = agent_info.agentId # Get generated ID
    session = lifecycle.start_session(agent_id, "wf_get_test")

    retrieved_session = lifecycle.get_session(session.sessionId)
    assert isinstance(retrieved_session, models.WorkflowSession)
    assert retrieved_session.sessionId == session.sessionId
    assert retrieved_session.agentId == session.agentId

def test_get_session_not_found():
    """Test getting a non-existent session returns None."""
    retrieved_session = lifecycle.get_session("non_existent_session")
    assert retrieved_session is None