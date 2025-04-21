import random
import time
import os
import json
from locust import HttpUser, task, between
from datetime import datetime, timezone

# Get Ops-Core API Key from environment variable
OPSCORE_API_KEY = os.environ.get("OPSCORE_API_KEY", "dummy_api_key")

# Load sample workflow definition
# Adjust path relative to the ops-core root where locust is likely run from
SAMPLE_WORKFLOW_PATH = "docs/sample_workflow.json"
try:
    with open(SAMPLE_WORKFLOW_PATH, "r") as f:
        SAMPLE_WORKFLOW = json.load(f)
except FileNotFoundError:
    print(f"Error: {SAMPLE_WORKFLOW_PATH} not found. Workflow task cannot run.")
    SAMPLE_WORKFLOW = None
except json.JSONDecodeError:
    print(f"Error: {SAMPLE_WORKFLOW_PATH} is not valid JSON.")
    SAMPLE_WORKFLOW = None

class OpsCoreUser(HttpUser):
    """
    Locust user class for Scenario 3: Mixed Realistic Load.
    Includes state updates, state retrieval, and workflow initiation
    with specified weighting.
    """
    # Default wait time for mixed load
    wait_time = between(1, 5)

    # Set the host from environment variable or default
    host = os.environ.get("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        """
        Called when a Locust user starts.
        Set the default headers for API Key authentication and register the agent.
        """
        self.client.headers = {"Authorization": f"Bearer {OPSCORE_API_KEY}"}
        # Generate a unique agent ID for each user instance
        self.agent_id = f"loadtest-agent-{random.randint(10000, 99999)}"
        print(f"Locust user starting with agent ID: {self.agent_id}")
        self.register_with_opscore() # Register the agent with Ops-Core

    def register_with_opscore(self):
        """
        Registers the agent with Ops-Core via the internal notification endpoint.
        """
        registration_payload = {
            "event_type": "REGISTER",
            "agent_details": {
                "agentId": self.agent_id,
                "agentName": f"LoadTestAgent-{self.agent_id}",
                "version": "1.0",
                # Add capabilities needed by the sample workflow and state reporting
                "capabilities": ["state_reporting", "test_capability", "another_capability"],
                "contactEndpoint": f"http://fake-agent-{self.agent_id}.local/run",
                "metadata": {"load_test_user": self.agent_id, "scenario": 3}
            }
        }
        with self.client.post("/v1/opscore/internal/agent/notify", json=registration_payload, catch_response=True, name="/v1/opscore/internal/agent/notify") as response:
            if response.status_code == 200:
                print(f"Successfully registered agent {self.agent_id} with Ops-Core.")
                response.success()
            else:
                print(f"Failed to register agent {self.agent_id} with Ops-Core. Status: {response.status_code}, Response: {response.text}")
                response.failure(f"Failed to register agent: {response.status_code}")

    @task(80) # Weight for Scenario 3
    def post_agent_state(self):
        """
        Simulates an agent sending a state update to Ops-Core.
        """
        state_payload = {
            "agentId": self.agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": random.choice(["idle", "active", "error", "finished"]),
            "details": {"load_test": True, "user": f"user-{self.agent_id}"}
        }
        self.client.post(f"/v1/opscore/agent/{self.agent_id}/state", json=state_payload, name="/v1/opscore/agent/[id]/state")

    @task(15) # Weight for Scenario 3
    def get_agent_state(self):
        """
        Simulates monitoring an agent's state.
        """
        self.client.get(f"/v1/opscore/agent/{self.agent_id}/state", name="/v1/opscore/agent/[id]/state")

    @task(5) # Weight for Scenario 3
    def post_agent_workflow(self):
        """
        Simulates triggering a workflow for the agent.
        """
        if SAMPLE_WORKFLOW:
            # Wrap the loaded sample workflow definition in the expected structure
            workflow_payload = SAMPLE_WORKFLOW
            wrapped_payload = {"workflowDefinition": workflow_payload}
            self.client.post(f"/v1/opscore/agent/{self.agent_id}/workflow", json=wrapped_payload, name="/v1/opscore/agent/[id]/workflow")
        else:
            # Skip task if workflow definition failed to load
            print(f"Skipping workflow task for {self.agent_id} due to missing/invalid {SAMPLE_WORKFLOW_PATH}")