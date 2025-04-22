# Plan: Fix Load Test Scenario 2 (Agent Registration)

**Date:** 2025-04-21

**Objective:** Resolve the 100% 500 Internal Server Error rate observed during Scenario 2 load testing (`load_tests/scenario_2/locustfile.py`) by implementing agent registration.

**Diagnosis:** The errors are caused by the Locust script attempting to trigger workflows for agents that have not been registered within the user's session, as confirmed by the lack of registration logic in the script's `on_start` method and the behavior of the Ops-Core API.

**Approach:** Adapt the successful agent registration logic and `on_start` structure from the working Scenario 1 script (`load_tests/scenario_1/locustfile.py`).

## Detailed Steps for Code Modification (`load_tests/scenario_2/locustfile.py`)

1.  **Add Imports:** Ensure the following imports are present at the top of the file:
    ```python
    import time
    import logging
    import uuid # Ensure uuid is imported if not already
    ```
2.  **Add Logger:** Add the logger instance below the imports:
    ```python
    logger = logging.getLogger(__name__)
    ```
3.  **Add `register_with_opscore` Method:** Add the following method inside the `WorkflowUser` class:
    ```python
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
        # Use logger for output
        with self.client.post("/v1/opscore/internal/agent/notify", json=registration_payload, catch_response=True, name="/v1/opscore/internal/agent/notify") as response:
            if response.status_code == 200:
                logger.info(f"Successfully registered agent {self.agent_id} with Ops-Core.")
                response.success()
            else:
                logger.error(f"Failed to register agent {self.agent_id} with Ops-Core. Status: {response.status_code}, Response: {response.text}")
                response.failure(f"Failed to register agent: {response.status_code}")
    ```
4.  **Replace `on_start` Method:** Replace the existing `on_start` method in the `WorkflowUser` class with the following:
    ```python
    def on_start(self):
        """
        Called when a Locust user starts.
        Registers the agent and waits for it to be available before starting tasks.
        """
        # Temporarily remove headers for registration
        original_headers = self.client.headers
        self.client.headers = {}

        # Generate a unique agent ID for each user instance
        # self.agent_id = f"workflow-agent-{random.randint(10000, 99999)}" # Original
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
                # Ensure headers are set for the GET request
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
    ```

## Verification Steps

1.  **Start Services:** Ensure Ops-Core, AgentKit (if needed by workflow), and Redis are running via Docker Compose:
    ```bash
    docker compose -f docker-compose.real-agentkit.yml up -d --build
    ```
2.  **Run Short Test:** Execute a brief Locust run from the workspace root (`ops-core`) to check for 500 errors:
    ```bash
    ./.venv/bin/locust -f load_tests/scenario_2/locustfile.py --headless --users 10 --spawn-rate 5 -t 30s --host http://localhost:8000
    ```
3.  **Analyze Output:** Check the Locust output for successful workflow initiation requests (e.g., HTTP 200 or 202) and the absence of 500 errors on the `/v1/opscore/agent/[id]/workflow` endpoint.

## Full Load Test (Post-Verification)

1.  **Execute Full Run:** If the verification step is successful, run the complete 18-minute Scenario 2 load test:
    ```bash
    ./.venv/bin/locust -f load_tests/scenario_2/locustfile.py --headless --users 50 --spawn-rate 10 -t 18m --host http://localhost:8000 > load_test_results_scenario2_full.txt 2>&1
    ```
2.  **Collect Results:** Analyze the generated `load_test_results_scenario2_full.txt` file and the Locust statistics (CSV files, HTML report if generated).

## Next Steps After Implementation

1.  Update `TASK.md` to reflect the completion of this debugging step for Task 4.4.
2.  Update `memory-bank/activeContext.md` and `memory-bank/progress.md` with the outcome.
3.  Proceed with the remaining load test scenarios (3 and 4) as outlined in `load_testing_plan.md`.