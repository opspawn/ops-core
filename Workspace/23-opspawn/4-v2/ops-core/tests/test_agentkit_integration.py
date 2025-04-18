import pytest
import requests
import os

# Define the URLs for the Ops-Core and AgentKit APIs
OPSCORE_API_URL = os.getenv("OPSCORE_API_URL", "http://localhost:8000")
AGENTKIT_API_URL = os.getenv("AGENTKIT_API_URL", "http://localhost:8001")

# Define a test API key
API_KEY = "test-api-key"

# Define a fixture for registering an agent
@pytest.fixture
def register_agent():
    agent_data = {
        "agentId": "test-agent",
        "agentName": "Test Agent",
        "version": "1.0",
        "capabilities": ["test"],
        "contactEndpoint": "http://test-agent:5000",
        "registrationTime": "2025-04-18T12:00:00Z",
        "metadata": {}
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}
    # Register the agent with AgentKit by sending a POST request to the /v1/agents endpoint
    response = requests.post(f"{AGENTKIT_API_URL}/v1/agents", headers=headers, json=agent_data)
    assert response.status_code == 200

    state_data = {
        "agentId": agent_data["agentId"],
        "timestamp": "2025-04-18T12:00:00Z",
        "state": "idle"
    }
    response = requests.post(f"{OPSCORE_API_URL}/v1/opscore/agent/{agent_data['agentId']}/state", headers=headers, json=state_data)
    assert response.status_code == 404
    return agent_data
# Test that an agent can be registered with Ops-Core
def test_register_agent():
    agent_data = {
        "agentId": "test-agent",
        "agentName": "Test Agent",
        "version": "1.0",
        "capabilities": ["test"],
        "contactEndpoint": "http://test-agent:5000",
        "registrationTime": "2025-04-18T12:00:00Z",
        "metadata": {}
    }
    # Register the agent with AgentKit by sending a POST request to the /v1/agents endpoint
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(f"{AGENTKIT_API_URL}/v1/agents", headers=headers, json=agent_data)
    assert response.status_code == 200

    # Verify that the agent is registered by checking the AgentKit API
    response = requests.get(f"{AGENTKIT_API_URL}/v1/agents")
    assert response.status_code == 200
    agents = response.json()["data"]
    assert any(agent["agentId"] == agent_data["agentId"] for agent in agents)


# Test that Ops-Core can dispatch a task to an agent
def test_dispatch_task(register_agent):
    agent_data = register_agent
    task_data = {
        "senderId": "opscore",
        "messageType": "test",
        "payload": {"task": "test task"}
    }
    response = requests.post(f"{AGENTKIT_API_URL}/v1/agents/{agent_data['agentId']}/run", json=task_data)
    assert response.status_code == 200