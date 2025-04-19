"""
Pytest configuration and shared fixtures for Ops-Core tests.
"""

import pytest
import sys
import os

# Ensure the opscore package is discoverable
# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import from opscore
try:
    from opscore import storage, workflow, models # Add workflow import
    from datetime import datetime
    from pydantic import HttpUrl
except ImportError as e:
    print(f"Error importing opscore modules in conftest.py: {e}")
    print(f"Project root added to path: {project_root}")
    print(f"Current sys.path: {sys.path}")
    # Re-raise the exception to make it clear there's an issue
    raise

@pytest.fixture(autouse=True)
def clear_storage_before_each_test():
    """
    Fixture to automatically clear the in-memory storage and task queue
    before each test runs.
    """
    print("\nClearing storage and queue before test...") # Added print for visibility
    storage.clear_all_data()
    # Clear the in-memory deque directly (specific to current implementation)
    if hasattr(workflow, '_task_queue'):
        workflow._task_queue.clear()
    yield # Test runs here
    print("Storage and queue cleared after test.") # Optional: confirm cleanup

# --- Sample Data Fixtures ---

@pytest.fixture(scope="session") # Session scope as these are read-only data
def valid_agent_reg_details_data() -> dict:
    """Provides valid raw data for AgentRegistrationDetails."""
    return {
        "agentId": "agent_test_123", # Added missing agentId
        "agentName": "TestAgent",
        "version": "1.0.1",
        "capabilities": ["test_capability", "another_one"],
        "contactEndpoint": "http://localhost:9000/testagent",
        "metadata": {"host": "testhost", "pid": 1234}
    }

@pytest.fixture(scope="session")
def valid_agent_reg_details(valid_agent_reg_details_data) -> models.AgentRegistrationDetails:
    """Provides a valid AgentRegistrationDetails model instance."""
    return models.AgentRegistrationDetails(**valid_agent_reg_details_data)

@pytest.fixture(scope="session")
def valid_agent_info(valid_agent_reg_details) -> models.AgentInfo:
    """Provides a valid AgentInfo model instance."""
    return models.AgentInfo(
        **valid_agent_reg_details.model_dump(),
        # agentId="agent_test_123", # Removed redundant agentId kwarg
        registrationTime=datetime(2024, 1, 1, 12, 0, 0) # Fixed time for predictability
    )

@pytest.fixture(scope="session")
def valid_agent_state_data() -> dict:
    """Provides valid raw data for AgentState."""
    return {
        "agentId": "agent_test_123",
        "state": "idle",
        "details": {"reason": "completed task xyz"},
        "timestamp": datetime(2024, 1, 1, 12, 5, 0) # Fixed time
    }

@pytest.fixture(scope="session")
def valid_agent_state(valid_agent_state_data) -> models.AgentState:
    """Provides a valid AgentState model instance."""
    return models.AgentState(**valid_agent_state_data)


@pytest.fixture(scope="session")
def valid_workflow_def_dict() -> dict:
    """Provides a dictionary representing a valid workflow definition."""
    return {
        "id": "wf_test_001",
        "name": "Test Workflow",
        "description": "A simple workflow for testing.",
        "version": "1.1",
        "tasks": [
            {"taskId": "task_A", "name": "First Task", "agentCapability": "cap_A", "parameters": {"p1": "v1"}, "nextTaskId": "task_B"},
            {"taskId": "task_B", "name": "Second Task", "agentCapability": "cap_B", "parameters": {"p2": "v2"}, "nextTaskId": None}
        ]
    }

@pytest.fixture(scope="session")
def valid_workflow_def_model(valid_workflow_def_dict) -> models.WorkflowDefinition:
    """Provides a valid WorkflowDefinition model instance."""
    return models.WorkflowDefinition(**valid_workflow_def_dict)

@pytest.fixture(scope="function") # Function scope as ID is generated dynamically
def valid_session_model() -> models.WorkflowSession:
    """Provides a valid WorkflowSession model instance."""
    # Note: sessionId, startTime, last_updated_time are auto-generated
    return models.WorkflowSession(
        workflowId="wf_test_001",
        agentId="agent_test_123",
        status="started"
    )

@pytest.fixture(scope="session")
def valid_task_data_dict() -> dict:
    """Provides a dictionary representing valid data for models.Task."""
    return {
        "taskId": "task_instance_abc",
        "workflowId": "wf_test_001",
        "sessionId": "session_xyz",
        "agentId": "agent_test_123",
        "taskDefinitionId": "task_A",
        "payload": {"p1": "v1_override"},
        "status": "pending",
        "retryCount": 0,
        "maxRetries": 2
        # createdAt, updatedAt are auto-generated
    }

# Add more fixtures as needed