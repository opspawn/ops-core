import random
import time
import os
import json
from locust import HttpUser, task, between
from datetime import datetime, timezone

# Get Ops-Core API Key from environment variable
OPSCORE_API_KEY = os.environ.get("OPSCORE_API_KEY", "dummy_api_key")

class OpsCoreUser(HttpUser):
    """
    Locust user class for Scenario 1: High State Update Load.
    Focuses solely on the POST /state endpoint.
    """
    # Wait time as defined in Scenario 1 plan
    wait_time = between(5, 10)

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
                # Capabilities needed for state reporting
                "capabilities": ["state_reporting"],
                "contactEndpoint": f"http://fake-agent-{self.agent_id}.local/run",
                "metadata": {"load_test_user": self.agent_id, "scenario": 1}
            }
        }
        with self.client.post("/v1/opscore/internal/agent/notify", json=registration_payload, catch_response=True, name="/v1/opscore/internal/agent/notify") as response:
            if response.status_code == 200:
                print(f"Successfully registered agent {self.agent_id} with Ops-Core.")
                response.success()
            else:
                print(f"Failed to register agent {self.agent_id} with Ops-Core. Status: {response.status_code}, Response: {response.text}")
                response.failure(f"Failed to register agent: {response.status_code}")

    @task(100) # Only task for Scenario 1
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