import pytest
import pytest_asyncio # Import pytest_asyncio
import httpx
import asyncio
import os
import subprocess
import time
from typing import AsyncGenerator, Dict, Any

# Define base URLs based on docker-compose service names/ports
# When running tests from the HOST, use localhost and mapped ports.
OPSCORE_BASE_URL = "http://localhost:8000" # Host port mapping
AGENTKIT_BASE_URL = "http://localhost:8001" # Host port mapping
SIMULATED_AGENT_BASE_URL = "http://localhost:8080" # Host port mapping

# --- Helper Functions ---

async def wait_for_service(url: str, service_name: str, timeout: int = 60):
    """Polls a service's health endpoint until it's available or timeout."""
    start_time = time.time()
    print(f"Checking {service_name} readiness at {url}/health...") # Check /health for all
    while time.time() - start_time < timeout:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/health") # Check /health
                if response.status_code == 200:
                    print(f"{service_name} is healthy.")
                    return True
        except httpx.RequestError:
            pass # Service not yet available
        await asyncio.sleep(2)
    raise TimeoutError(f"{service_name} did not become healthy within {timeout} seconds.")

async def poll_for_agent_state(base_url: str, agent_id: str, expected_state: str, timeout: int = 30) -> Dict[str, Any]:
    """Polls Ops-Core state endpoint for a specific agent state."""
    # print(f"DEBUG: Type of client received in poll_for_agent_state: {type(client)}") # DEBUG line removed
    start_time = time.time()
    last_state = None
    # Use the same API key defined in docker-compose for Ops-Core
    api_key = "test-api-key"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client: # Create client inside
        while time.time() - start_time < timeout:
            try:
                # Add the Authorization header to the request
                response = await client.get(f"/v1/opscore/agent/{agent_id}/state", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Extract state directly from the top-level response data
                    last_state = data.get("state")
                    # Check for expected state *only* if response was successful
                    if last_state == expected_state:
                        print(f"Agent {agent_id} reached expected state '{expected_state}'.")
                        return data # Return the full state info
                elif response.status_code == 404:
                    # Agent might not be registered yet, print info and continue polling
                    print(f"Polling state for {agent_id}: Agent not found (404).")
                    last_state = 'not_found' # Update last_state for timeout message
                    pass
                else:
                    # Raise unexpected HTTP errors
                    print(f"Polling state for {agent_id}: Received unexpected status {response.status_code}")
                    response.raise_for_status()
            except httpx.RequestError as e:
                 print(f"Polling state for {agent_id}: Network error {e}")
            except Exception as e:
                print(f"Polling state for {agent_id}: Unexpected error {e}")

            await asyncio.sleep(1) # Wait before next poll attempt

    raise TimeoutError(f"Agent {agent_id} did not reach state '{expected_state}' within {timeout} seconds. Last state: {last_state}")


# --- Pytest Fixtures ---

# @pytest.fixture(scope="module", autouse=True)
# def docker_compose_up_down():
#     """Starts and stops the docker-compose services for the module."""
#     # NOTE: This fixture is problematic when running tests INSIDE the container via `docker-compose run`
#     # because docker-compose is not available inside the container.
#     # The `docker-compose run` command itself should handle service startup based on depends_on.
#     compose_file = "docker-compose.real-agentkit.yml"
#     project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) # Get project root
#
#     print(f"\nStarting services from {compose_file}...")
#     # Use --wait for services that support it, otherwise rely on health checks
#     # Added --remove-orphans to clean up potential old containers
#     # Added --force-recreate to ensure fresh state
#     # Added --build to ensure images are up-to-date
#     start_command = ["docker-compose", "-f", compose_file, "up", "-d", "--build", "--force-recreate", "--remove-orphans"]
#     # subprocess.run(start_command, check=True, cwd=project_dir) # Problematic line
#
#     # Wait for services to be healthy (implement health checks in services)
#     # try:
#     #     # Wait for Ops-Core (assuming /health endpoint exists)
#     #     asyncio.run(wait_for_service(f"{OPSCORE_BASE_URL}", "Ops-Core"))
#     #     # Wait for AgentKit (assuming /health endpoint exists)
#     #     asyncio.run(wait_for_service(f"{AGENTKIT_BASE_URL}", "AgentKit"))
#     #      # Wait for Simulated Agent
#     #     asyncio.run(wait_for_service(f"{SIMULATED_AGENT_BASE_URL}", "Simulated Agent"))
#     #     print("All services are healthy.")
#     # except TimeoutError as e:
#     #     print(f"Service health check failed: {e}")
#     #     # Attempt to show logs before tearing down
#     #     log_command = ["docker-compose", "-f", compose_file, "logs"]
#     #     # subprocess.run(log_command, cwd=project_dir) # Problematic line
#     #     pytest.fail(f"Failed to start services: {e}")
#
#
#     yield # Run tests
#
#     print(f"\nStopping services from {compose_file}...")
#     stop_command = ["docker-compose", "-f", compose_file, "down", "--remove-orphans"]
#     # subprocess.run(stop_command, check=True, cwd=project_dir) # Problematic line
#
@pytest_asyncio.fixture(scope="function") # Change scope to function
async def opscore_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for interacting with the Ops-Core service."""
    async with httpx.AsyncClient(base_url=OPSCORE_BASE_URL, timeout=30.0) as client:
        yield client

@pytest_asyncio.fixture(scope="function") # Change scope to function
async def agentkit_client() -> httpx.AsyncClient:
    """HTTP client for interacting with the AgentKit service."""
    client = httpx.AsyncClient(base_url=AGENTKIT_BASE_URL, timeout=30.0)
    yield client
    await client.aclose() # Close the client after the function test is done

# --- Test Cases ---

@pytest.mark.asyncio
async def test_end_to_end_workflow(opscore_client: httpx.AsyncClient, agentkit_client: httpx.AsyncClient): # Add agentkit_client fixture
    """
    Tests the full workflow:
    1. Simulated Agent registers with AgentKit (on startup).
    2. Ops-Core receives webhook and registers agent internally.
    3. Test triggers a workflow via Ops-Core API.
    4. Ops-Core dispatches task to AgentKit.
    5. AgentKit forwards task to Simulated Agent.
    6. Simulated Agent reports 'active' state to Ops-Core.
    7. Simulated Agent reports 'idle' state to Ops-Core.
    """
    # 1. Wait for services to be healthy
    print("Waiting for services to be healthy...")
    try:
        # Wait for Ops-Core
        await wait_for_service(OPSCORE_BASE_URL, "Ops-Core")
        # Wait for AgentKit
        await wait_for_service(AGENTKIT_BASE_URL, "AgentKit")
        # Wait for Simulated Agent
        await wait_for_service(SIMULATED_AGENT_BASE_URL, "Simulated Agent")
        print("All services are healthy.")
    except TimeoutError as e:
        pytest.fail(f"Service health check failed: {e}")


    # 2. Discover the dynamically generated agent ID from the Simulated Agent's health endpoint
    print("Discovering agent ID from Simulated Agent...")
    discovered_agent_id = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATED_AGENT_BASE_URL}/health")
            response.raise_for_status()
            health_data = response.json()
            discovered_agent_id = health_data.get("agent_id")
            if not discovered_agent_id:
                 pytest.fail("Simulated Agent health endpoint did not return 'agent_id'.")
            print(f"Discovered agent ID from Simulated Agent: {discovered_agent_id}")
    except Exception as e:
        pytest.fail(f"Failed to discover agent ID from Simulated Agent health endpoint: {e}")


    # Add a small delay to allow Ops-Core to process the registration webhook
    print("Waiting 5 seconds for Ops-Core to process registration webhook...")
    await asyncio.sleep(5)
    print("Continuing test...")

    # 3. Verify Agent Registration in Ops-Core (via webhook)
    # Step 3a: Poll for the initial "UNKNOWN" state set by webhook processing
    print(f"Verifying initial registration (state UNKNOWN) of agent {discovered_agent_id} in Ops-Core...")
    try:
        await poll_for_agent_state(OPSCORE_BASE_URL, discovered_agent_id, "UNKNOWN", timeout=30) # Check for UNKNOWN first
        print(f"Agent {discovered_agent_id} successfully registered in Ops-Core (state UNKNOWN found).")
    except TimeoutError:
        pytest.fail(f"Agent {discovered_agent_id} did not reach state UNKNOWN in Ops-Core after startup webhook.")

    # Step 3b: Now wait for the agent to report itself as "idle"
    print(f"Waiting for agent {discovered_agent_id} to report state IDLE...")
    try:
        await poll_for_agent_state(OPSCORE_BASE_URL, discovered_agent_id, "idle", timeout=30) # Now wait for IDLE
        print(f"Agent {discovered_agent_id} reported state IDLE.")
    except TimeoutError:
        pytest.fail(f"Agent {discovered_agent_id} did not report state IDLE after registration.")

    # 4: Trigger Workflow
    print(f"Triggering workflow for agent {discovered_agent_id}...")
    workflow_payload = {
        "workflow_name": "simulated_test_workflow",
        # Define a simple inline workflow
        "definition": {
            "description": "Simple test workflow for simulation",
            "tasks": [
                {
                    "task_id": "sim_task_1",
                    "task_name": "simulation_step",
                    "parameters": {"duration": 2}
                }
            ]
        }
    }
    # Use the opscore_client fixture here
    trigger_response = await opscore_client.post(f"/v1/opscore/agent/{discovered_agent_id}/workflow", json=workflow_payload)
    assert trigger_response.status_code == 202 # Expect 202 Accepted for async trigger
    print(f"Workflow triggered successfully for agent {discovered_agent_id}.")
    # TODO: Potentially extract session ID if needed

    # 5, 6, 7: Verify Agent becomes 'active' and then 'idle'
    print(f"Waiting for agent {discovered_agent_id} to become active...")
    try:
        await poll_for_agent_state(OPSCORE_BASE_URL, discovered_agent_id, "active", timeout=30)
        print(f"Agent {discovered_agent_id} is now active.")
    except TimeoutError:
        pytest.fail(f"Agent {discovered_agent_id} did not become active.")

    print(f"Waiting for agent {discovered_agent_id} to become idle...")
    try:
        await poll_for_agent_state(OPSCORE_BASE_URL, discovered_agent_id, "idle", timeout=30)
        print(f"Agent {discovered_agent_id} is now idle. Workflow complete.")
    except TimeoutError:
        pytest.fail(f"Agent {discovered_agent_id} did not return to idle.")

# TODO: Add more test cases for error handling, different workflow types, etc.