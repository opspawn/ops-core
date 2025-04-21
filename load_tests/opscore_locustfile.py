import random
import time
import os
from locust import HttpUser, task, between, constant
from datetime import datetime, timezone # Import datetime and timezone

# Get Ops-Core API Key from environment variable
# This should be set when running Locust, e.g., OPSCORE_API_KEY=your_key locust -f ...
OPSCORE_API_KEY = os.environ.get("OPSCORE_API_KEY", "dummy_api_key") # Use a dummy key if not set

class OpsCoreUser(HttpUser):
    """
    Locust user class to simulate load on Ops-Core API endpoints.
    """
    # wait_time = between(1, 2) # Wait 1-2 seconds between tasks
    # Using constant wait time for more predictable request rate in minimal test
    wait_time = constant(1)

    # Set the host from environment variable or default
    # This should be set when running Locust, e.g., LOCUST_HOST=http://localhost:8000 locust -f ...
    host = os.environ.get("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        """
        Called when a Locust user starts.
        Set the default headers for API Key authentication and register the agent.
        """
        self.client.headers = {"Authorization": f"Bearer {OPSCORE_API_KEY}"}
        self.agent_id = f"loadtest-agent-{random.randint(1000, 9999)}"
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
                "capabilities": ["state_reporting"],
                "contactEndpoint": f"http://fake-agent-{self.agent_id}.local/run", # Placeholder endpoint
                "metadata": {"load_test_user": self.agent_id}
            }
        }
        # Use catch_response=True to ensure we handle non-200 responses
        with self.client.post("/v1/opscore/internal/agent/notify", json=registration_payload, catch_response=True, name="/v1/opscore/internal/agent/notify") as response:
            if response.status_code == 200:
                print(f"Successfully registered agent {self.agent_id} with Ops-Core.")
                response.success()
            else:
                print(f"Failed to register agent {self.agent_id} with Ops-Core. Status: {response.status_code}, Response: {response.text}")
                response.failure(f"Failed to register agent: {response.status_code}")


    @task
    def post_agent_state(self):
        """
        Simulates an agent sending a state update to Ops-Core.
        This task is used for the minimal load test (Scenario 0).
        """
        state_payload = {
            "agentId": self.agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": random.choice(["idle", "active", "error", "finished"]),
            "details": {"load_test": True, "user": f"user-{self.agent_id}"} # Use agent_id for user identification
        }
        # Use catch_response=True to manually mark success/failure if needed,
        # but for basic check, default status code handling is fine.
        self.client.post(f"/v1/opscore/agent/{self.agent_id}/state", json=state_payload, name="/v1/opscore/agent/[id]/state")

# Note: For Scenario 0, we will configure the number of users and spawn rate
# via the Locust web UI or CLI when running the test, as per the plan.
# The tasks defined above will be executed by the users.

# To run this minimal test (Scenario 0):
# 1. Ensure Ops-Core and Redis are running via docker-compose.real-agentkit.yml
# 2. Set the OPSCORE_API_KEY environment variable.
# 3. Run locust from the terminal in the ops-core directory:
#    OPSCORE_API_KEY=your_api_key LOCUST_HOST=http://localhost:8000 locust -f load_tests/opscore_locustfile.py
# 4. Open the Locust web UI (http://localhost:8089) and set:
#    Number of users: 5
#    Spawn rate: 5 (users per second)
#    Host: http://localhost:8000 (should be pre-filled from LOCUST_HOST env var)
# 5. Click "Start swarming!" and observe the results for 5 minutes.