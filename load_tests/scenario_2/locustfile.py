import random
import time
import os
import json
import logging # Added
import uuid # Added
from locust import HttpUser, task, between, constant
from datetime import datetime, timezone

# Added logger
logger = logging.getLogger(__name__)

# Get Ops-Core API Key from environment variable
OPSCORE_API_KEY = os.environ.get("OPSCORE_API_KEY", "dummy_api_key")

# Sample workflow definition from docs/sample_workflow.json
SAMPLE_WORKFLOW_DEFINITION = {
  "id": "sample_workflow_id",
  "name": "Sample Load Test Workflow",
  "description": "A simple workflow for performance testing.",
  "version": "1.0",
  "tasks": [
    {
      "taskId": "step_1",
      "name": "First Step",
      "agentCapability": "test_capability",
      "parameters": {
        "message": "This is the first step."
      },
      "nextTaskId": "step_2"
    },
    {
      "taskId": "step_2",
      "name": "Second Step",
      "agentCapability": "another_capability",
      "parameters": {
        "value": 123
      },
      "nextTaskId": None
    }
  ]
}

class WorkflowUser(HttpUser):
    """
    Locust user class for Scenario 2: Workflow Initiation Load.
    Focuses on the POST /workflow endpoint.
    """
    # Wait time as defined in Scenario 2 plan (30 to 60 seconds between tasks)
    wait_time = between(30, 60)

    # Set the host from environment variable or default
    host = os.environ.get("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        """
        Called when a Locust user starts.
        Registers the agent and waits for it to be available before starting tasks.
        """
        # Temporarily remove headers for registration
        original_headers = self.client.headers
        self.client.headers = {}

        # Generate a unique agent ID for each user instance
        self.agent_id = f"workflow-agent-{uuid.uuid4()}" # Use UUID for better uniqueness
        logger.info(f"Locust user starting with agent ID: {self.agent_id}")

        self.register_with_opscore() # Register the agent with Ops-Core
        time.sleep(1) # Add a small delay to allow state to be saved

        # Restore original headers for subsequent tasks
        self.client.headers = original_headers
        # Ensure API key is set for subsequent requests
        self.client.headers["Authorization"] = f"Bearer {OPSCORE_API_KEY}"

        logger.debug(f"Headers after restoration in on_start: {self.client.headers}")

        # Wait for agent state to be available
        timeout = 15  # Increased timeout slightly
        start_time = time.time()
        state_available = False
        while time.time() - start_time < timeout:
            try:
                # Headers are set on self.client.headers, no need to pass explicitly
                state_response = self.client.get(f"/v1/opscore/agent/{self.agent_id}/state", name="/v1/opscore/agent/[id]/state")
                if state_response.status_code == 200:
                    state_data = state_response.json()
                    if state_data is not None: # Check if response body is not empty/null
                        logger.info(f"Agent {self.agent_id} state available: {state_data.get('state', 'N/A')}")
                        state_available = True
                        break
                    else:
                         logger.warning(f"Agent {self.agent_id} state check returned 200 but with empty body.")
                elif state_response.status_code == 404:
                    logger.warning(f"Agent {self.agent_id} not found yet (404). Retrying...")
                else:
                    logger.error(f"Error checking agent state for {self.agent_id}: Status {state_response.status_code}, Response: {state_response.text}")

            except Exception as e:
                logger.error(f"Exception checking agent state for {self.agent_id}: {e}")
            time.sleep(1.0) # Increased sleep interval slightly

        if not state_available:
            logger.error(f"Timeout waiting for agent {self.agent_id} state after {timeout} seconds.")
            # Optionally fail the user if state is not available within timeout
            # self.environment.runner.quit()

    def register_with_opscore(self):
        """
        Registers the agent with Ops-Core via the internal notification endpoint.
        """
        registration_payload = {
            "event_type": "REGISTER",
            "agent_details": {
                "agentId": self.agent_id,
                "agentName": f"LoadTestAgent-{self.agent_id}", # Keep consistent naming if desired
                "version": "1.0",
                # Add capabilities relevant to workflow if needed, otherwise keep minimal
                "capabilities": ["workflow_execution"], # Example capability
                "contactEndpoint": f"http://fake-agent-{self.agent_id}.local/run",
                "metadata": {"load_test_user": self.agent_id, "scenario": 2} # Updated scenario number
            }
        }
        # Use logger for output and catch_response for explicit success/failure marking
        with self.client.post("/v1/opscore/internal/agent/notify", json=registration_payload, catch_response=True, name="/v1/opscore/internal/agent/notify") as response:
            if response.status_code == 200:
                logger.info(f"Successfully registered agent {self.agent_id} with Ops-Core.")
                response.success()
            else:
                logger.error(f"Failed to register agent {self.agent_id} with Ops-Core. Status: {response.status_code}, Response: {response.text}")
                response.failure(f"Failed to register agent: {response.status_code}")

    @task(1) # Task weight of 1
    def trigger_workflow(self):
        """
        Simulates triggering a workflow for the agent.
        """
        # Send only the workflow_id, assuming the definition is pre-loaded on the server
        workflow_payload = {
            "agentId": self.agent_id,
            "workflowDefinitionId": SAMPLE_WORKFLOW_DEFINITION["id"], # Use the correct key name
            "context": {"load_test": True, "user": f"user-{self.agent_id}", "scenario": 2}
        }
        # Use catch_response=True to manually mark success/failure if needed
        # Headers are set on self.client.headers, no need to pass explicitly
        self.client.post(f"/v1/opscore/agent/{self.agent_id}/workflow", json=workflow_payload, name="/v1/opscore/agent/[id]/workflow")