import pytest
import httpx
import os
import asyncio
from datetime import datetime, timezone

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Configuration ---
# When running tests via 'docker-compose exec opscore ...':
# - Ops-Core is accessible via localhost:8000
# - AgentKit is accessible via its service name ('agentkit_service') and internal port (80)
OPSCORE_API_URL = os.getenv("OPSCORE_API_URL", "http://localhost:8000")
AGENTKIT_API_URL = os.getenv("AGENTKIT_API_URL", "http://agentkit_service:80") # Corrected default
API_KEY = os.getenv("OPSCORE_API_KEY", "test-api-key") # Use the key Ops-Core expects

# --- Test Data ---
TEST_AGENT_ID = "integration-test-agent-001"
AGENT_REGISTRATION_DATA = {
    "agentId": TEST_AGENT_ID,
    "agentName": "Integration Test Agent",
    "version": "1.1",
    "capabilities": ["integration_test"],
    "contactEndpoint": "http://fake-agent:1234",
    "registrationTime": datetime.now(timezone.utc).isoformat(), # Mock AgentKit expects string
    "metadata": {"test_run": "pytest"}
}

# --- Helper Functions ---
async def get_opscore_agent_state(client: httpx.AsyncClient, agent_id: str) -> httpx.Response:
    """Helper to get agent state from Ops-Core."""
    url = f"{OPSCORE_API_URL}/v1/opscore/agent/{agent_id}/state"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        return await client.get(url, headers=headers)
    except httpx.ConnectError as e:
        pytest.fail(f"Connection to Ops-Core ({url}) failed: {e}")

# --- Tests ---

async def test_agent_registration_via_webhook():
    """
    Test that registering an agent via AgentKit triggers the webhook # Corrected indentation (4 spaces)
    and successfully registers the agent in Ops-Core. # Corrected indentation (4 spaces)
    """ # Corrected indentation (4 spaces)
    async with httpx.AsyncClient(timeout=10.0) as client: # Corrected indentation (4 spaces)
        # 1. Register agent with Mock AgentKit # Corrected indentation (8 spaces)
        register_url = f"{AGENTKIT_API_URL}/v1/agents" # Corrected indentation (8 spaces)
        # Note: Mock AgentKit doesn't require auth for registration in current setup # Corrected indentation (8 spaces)
        response = await client.post(register_url, json=AGENT_REGISTRATION_DATA) # Corrected indentation (8 spaces)
        assert response.status_code == 200 # Corrected indentation (8 spaces)
        assert "webhook notification attempted" in response.json().get("message", "") # Corrected indentation (8 spaces)

        # 2. Wait briefly for webhook processing # Corrected indentation (8 spaces)
        await asyncio.sleep(0.5) # Allow time for the webhook call and processing # Corrected indentation (8 spaces)

        # 3. Verify agent state in Ops-Core # Corrected indentation (8 spaces)
        state_response = await get_opscore_agent_state(client, TEST_AGENT_ID) # Corrected indentation (8 spaces)
        assert state_response.status_code == 200 # Corrected indentation (8 spaces)
        state_data = state_response.json() # Corrected indentation (8 spaces)
        assert state_data["agentId"] == TEST_AGENT_ID # Corrected indentation (8 spaces)
        # Check initial state (depends on lifecycle.register_agent implementation) # Corrected indentation (8 spaces)
        # Assuming it registers as 'UNKNOWN' or 'IDLE' initially. Let's check for non-error state. # Corrected indentation (8 spaces)
        assert state_data["state"] is not None # Corrected indentation (8 spaces)
        assert state_data["state"].lower() != "error"
        # Let's assume initial state is UNKNOWN as per typical registration flow
        assert state_data["state"] == "UNKNOWN" # Or "IDLE" if register_agent sets it

async def test_agent_state_update_callback():
    """
    Test that when Mock AgentKit receives a task, it calls back to Ops-Core
    to update the agent's state (BUSY -> IDLE).
    """
    agent_id = f"state-update-agent-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    registration_data = {**AGENT_REGISTRATION_DATA, "agentId": agent_id}

    async with httpx.AsyncClient(timeout=10.0) as client: # Increased timeout
        # 1. Register agent via AgentKit (triggers webhook to Ops-Core)
        register_url = f"{AGENTKIT_API_URL}/v1/agents"
        response = await client.post(register_url, json=registration_data)
        assert response.status_code == 200
        await asyncio.sleep(0.5) # Wait for webhook

        # Verify initial state in Ops-Core
        state_response = await get_opscore_agent_state(client, agent_id)
        assert state_response.status_code == 200
        initial_state = state_response.json()["state"]
        assert initial_state == "UNKNOWN" # Or "IDLE"

        # 2. Trigger the mock agent's /run endpoint (simulating Ops-Core dispatch)
        run_url = f"{AGENTKIT_API_URL}/v1/agents/{agent_id}/run"
        task_payload = {"taskId": "task-123", "data": "run test"}
        # Note: Mock AgentKit /run doesn't require auth in current setup
        run_response = await client.post(run_url, json=task_payload)
        assert run_response.status_code == 200
        assert "state updates attempted" in run_response.json().get("message", "")

        # 3. Poll Ops-Core for state changes (BUSY then IDLE)
        final_state = None
        for _ in range(10): # Poll for up to 5 seconds (10 * 0.5s)
            await asyncio.sleep(0.5)
            state_response = await get_opscore_agent_state(client, agent_id)
            if state_response.status_code == 200:
                current_state = state_response.json()["state"]
                # Check if we reached the final expected state (IDLE)
                if current_state == "IDLE":
                    final_state = current_state
                    break
                # Optionally check for intermediate BUSY state if needed
                # elif current_state == "BUSY":
                #     # Saw busy state, continue polling for IDLE
                #     pass
            else:
                # Log unexpected status during polling
                print(f"Polling state failed: {state_response.status_code} - {state_response.text}")

        assert final_state == "IDLE", f"Agent did not reach IDLE state after task run. Last state: {current_state if 'current_state' in locals() else 'UNKNOWN'}"

# TODO: Add tests for DEREGISTER webhook (once implemented)
# TODO: Add tests for workflow triggering that involves these state updates