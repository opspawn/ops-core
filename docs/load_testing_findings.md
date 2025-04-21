# Load Testing Setup Findings and Debugging Notes

This document summarizes the issues encountered and their resolutions during the initial setup and debugging of the load testing environment using Locust for the Ops-Core API (Task 4.4).

## Initial Setup Issues and Resolutions (Scenario 0)

1.  **Locust command not found:**
    *   **Issue:** Attempting to run `locust` directly from the terminal resulted in a "command not found" error.
    *   **Reason:** Locust was installed within the project's Python virtual environment (`.venv`), and the terminal session was not activated to use this environment's executables.
    *   **Resolution:** Execute the `locust` module using the Python interpreter from the virtual environment: `./.venv/bin/python -m locust ...`.

2.  **`AttributeError: 'OpsCoreUser' object has no attribute 'get_request_meta'`:**
    *   **Issue:** The Locust test script (`load_tests/opscore_locustfile.py`) failed with an `AttributeError`.
    *   **Reason:** The script incorrectly attempted to use `self.get_request_meta()`, which is not a valid method on the `locust.HttpUser` class.
    *   **Resolution:** Removed the calls to `self.get_request_meta()` from the Locustfile.

3.  **`401 Client Error: Unauthorized`:**
    *   **Issue:** Requests from Locust to the Ops-Core API endpoint (`/v1/opscore/agent/{agentId}/state`) returned a `401 Unauthorized` error.
    *   **Reason:** The API key provided by Locust did not match the key expected by the Ops-Core service running in the Docker environment. The Ops-Core service loads its expected API key from the `.env` file, while the Locust script was initially using a placeholder or an incorrect key passed via environment variable.
    *   **Resolution:** Ensured the correct API key (`"test-api-key"`, as defined in `.env` and used by other services in `docker-compose.real-agentkit.yml`) was explicitly passed as an environment variable (`OPSCORE_API_KEY=test-api-key`) when executing the Locust command.

4.  **`404 Client Error: Not Found`:**
    *   **Issue:** Requests to the agent state update endpoint (`/v1/opscore/agent/{agentId}/state`) returned a `404 Not Found` error after the authentication issue was resolved.
    *   **Reason:** The randomly generated agent ID used by each Locust user was not registered with the Ops-Core service before state updates were attempted for that ID.
    *   **Resolution:** Modified the `load_tests/opscore_locustfile.py` to include a step in the `on_start` method to register the agent with Ops-Core's internal notification endpoint (`POST /v1/opscore/internal/agent/notify`) using the generated `agentId`. This endpoint does not require the API key.

## Findings and Challenges During Scenario Execution (Scenarios 1 & 2)

1.  **Scenario 1 Failures (`RemoteDisconnected`):**
    *   **Finding:** The full 20-minute run of Scenario 1 (High State Update Load) completed its duration but reported 40 failures (`RemoteDisconnected('Remote end closed connection without response')`) for the `POST /v1/opscore/agent/[id]/state` endpoint.
    *   **Challenge:** The Ops-Core service appears to become unstable or overwhelmed under the load of 500 concurrent users sending state updates, leading to dropped connections.
    *   **Status:** Identified. Requires further investigation into Ops-Core's performance under this specific load profile. Results are saved in `load_tests/scenario_1/`.

2.  **Scenario 2 Initial Failure (`422 Unprocessable Entity`):**
    *   **Finding:** The first attempt to run Scenario 2 (Workflow Initiation Load) failed immediately with a `422 Unprocessable Entity` error on the `POST /v1/opscore/agent/[id]/workflow` endpoint.
    *   **Reason:** The JSON payload for the workflow trigger was not wrapped in the `workflowDefinition` key as expected by the API's `WorkflowTriggerRequest` Pydantic model.
    *   **Solution:** Modified the locustfiles for Scenarios 2, 3, and 4 to correctly format the workflow trigger payload by wrapping the workflow definition in `{"workflowDefinition": ...}`.

3.  **Scenario 2 Second Failure (`ConnectionRefusedError`):**
    *   **Finding:** The second attempt to run Scenario 2 failed with `ConnectionRefusedError` and registration failures.
    *   **Reason:** The Docker containers for the test environment had stopped running.
    *   **Solution:** Restarted the Docker containers using `docker compose -f docker-compose.real-agentkit.yml up --build -d`.

4.  **Scenario 2 Third Failure (Quick Test - `500 Internal Server Error` and Registration Failures):**
    *   **Finding:** A quick 30-second test for Scenario 2, after applying the workflow payload fix and restarting Docker, still resulted in 100% failures for both `POST /v1/opscore/agent/[id]/workflow` (`500 Server Error: Internal Server Error`) and `POST /v1/opscore/internal/agent/notify` ("Failed to register agent: 0").
    *   **Challenge:** The Ops-Core service is encountering internal errors when attempting to trigger workflows and agents are failing to register, even under minimal load in this quick test. This indicates a deeper issue than just load capacity, possibly related to the workflow processing logic or interaction with the simulated agent/storage after a restart.
    *   **Status:** Identified. Requires immediate debugging of the Ops-Core service logs and code related to agent registration and workflow initiation.

## Best Practices / Learnings

*   Always execute Python tools installed in a virtual environment using the virtual environment's Python interpreter (`./.venv/bin/python -m ...`).
*   Carefully review the documentation and available methods for libraries/frameworks (e.g., Locust's `HttpUser` class) to avoid using non-existent functions.
*   Verify API key configurations across all interacting services (load test client, target service, other dependent services) to ensure consistency. Check `.env` files and Docker Compose configurations.
*   For APIs requiring resource registration (like agents in Ops-Core), ensure the load test script includes the necessary registration steps before attempting operations on those resources.
*   Use headless mode (`--headless`) and output redirection (`> output.txt 2>&1`) for running command-line tools like Locust to capture full output for analysis.
*   Start with minimal load and short durations during initial setup and debugging to quickly identify and resolve issues before running full-scale tests.
*   **New Learning:** When encountering persistent failures, especially `ConnectionRefusedError` or registration issues, verify that all necessary dependent services (like Docker containers) are running and accessible.
*   **New Learning:** `422 Unprocessable Entity` errors often indicate a mismatch between the request payload structure and the API's expected schema (check Pydantic models).
*   **New Learning:** `500 Internal Server Error` during load testing requires examining the *server's* logs (in this case, the Ops-Core Docker container logs) to understand the specific exception or error occurring within the application.

These findings will help streamline future load testing efforts and debugging processes.