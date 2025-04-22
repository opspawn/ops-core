# Debugging Plan: Agent Registration Failures (Task 4.4)

**Objective:** Identify and resolve the root cause of agent registration failures (`Failed to register agent: 0`, `ConnectionResetError`) observed during load testing Scenarios 1 and 2.

**Steps:**

1.  **Environment Reset:**
    *   Bring down all currently running Docker containers to ensure a clean state.
    *   Bring up the necessary Docker containers for the load testing environment, including Ops-Core, AgentKit, and Redis, using the appropriate Docker Compose file (`docker-compose.real-agentkit.yml`).

2.  **Initial Test Run:**
    *   Execute load testing Scenario 1 (`load_tests/scenario_1/locustfile.py`) using Locust.
    *   Configure the test to run for a short duration (e.g., 15 seconds) to quickly observe initial registration behavior and errors.
    *   Redirect the Locust output to a file (e.g., `locust_scenario_1_short_run.txt`) for detailed analysis.

3.  **Output Analysis:**
    *   Review the output file (`locust_scenario_1_short_run.txt`) for specific error messages, focusing on:
        *   Agent registration failures (status codes, error messages).
        *   `ConnectionResetError` occurrences.
        *   Any other relevant errors or warnings.
    *   Examine the Ops-Core logs (`opscore_error_logs.txt`, `opscore_registration_logs.txt`) and potentially the Redis container logs (`docker logs <redis_container_name>`) for corresponding errors or unusual activity during the test run.

4.  **Root Cause Investigation:**
    *   Based on the analysis from Step 3, pinpoint the likely area of failure. This could involve:
        *   Investigating the `/v1/opscore/internal/agent/notify` endpoint implementation in `opscore/api.py`.
        *   Examining the `lifecycle.register_agent` function in `opscore/lifecycle.py`.
        *   Reviewing the storage interaction within `lifecycle.register_agent` and the relevant methods in `opscore/storage.py` (specifically for the Redis implementation).
        *   Checking for potential issues with the Redis configuration or connectivity from within the Ops-Core container.
        *   Analyzing the Locust client's behavior during registration attempts.

5.  **Implement Fixes:**
    *   Based on the root cause identified in Step 4, implement the necessary code changes in the relevant Ops-Core files (`opscore/api.py`, `opscore/lifecycle.py`, `opscore/storage.py`).
    *   Consider adding more detailed logging in the registration path to aid future debugging if needed.

6.  **Verification:**
    *   Repeat Step 1 (Environment Reset).
    *   Repeat Step 2 (Initial Test Run) with the implemented fixes.
    *   Analyze the output to confirm that the agent registration failures and connection resets are resolved.

7.  **Full Load Test Execution (if fixes are successful):**
    *   If the registration issue is resolved, proceed with executing the full load testing scenarios (Scenario 1, 2, 3, and 4) as defined in `load_testing_plan.md`.
    *   Analyze the results of the full load tests to identify any performance bottlenecks or other issues.

**Mermaid Diagram of the Debugging Process:**

```mermaid
graph TD
    A[Start Debugging] --> B{Analyze Logs & Summary};
    B --> C[Formulate Initial Plan];
    C --> D[Reset Docker Environment];
    D --> E[Run Short Load Test (Scenario 1, 15s)];
    E --> F[Analyze Test Output & Logs];
    F --> G{Identify Root Cause?};
    G -- Yes --> H[Implement Fixes];
    G -- No --> I[Add More Logging/Investigation];
    I --> E; %% Loop back to test with more info
    H --> J[Reset Docker Environment];
    J --> K[Run Short Load Test (Scenario 1, 15s)];
    K --> L{Fix Verified?};
    L -- Yes --> M[Execute Full Load Tests];
    L -- No --> F; %% Loop back to analyze and refine fixes
    M --> N[Analyze Full Test Results];
    N --> O[Document Findings & Recommendations];
    O --> P[End Debugging Task];