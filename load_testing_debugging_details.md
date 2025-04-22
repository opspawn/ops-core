# Load Testing Debugging Details: Agent Registration Failures (Task 4.4)

**Date:** 2025-04-21

**Objective:** Continue debugging agent registration failures (`Failed to register agent: 0`, `ConnectionResetError`) observed during load testing Scenarios 1 and 2.

**Initial Blockers & Resolutions:**

1.  **Inability to Access Ops-Core Container Logs:**
    *   **Issue:** Could not retrieve logs from the `opscore_service_real` Docker container using `docker logs`.
    *   **Diagnosis:** Examined `Dockerfile` and `docker-compose.real-agentkit.yml`. Suspected the `--reload` flag in the Docker Compose command might interfere with logging.
    *   **Resolution:** Removed the `--reload` flag from the `opscore` service command in `docker-compose.real-agentkit.yml`.
    *   **Verification:** `docker logs opscore_service_real` successfully showed container output.

2.  **Syntax/Indentation Errors in Ops-Core Files:**
    *   **Issue:** After resolving log access, `docker logs` revealed `SyntaxError` and `IndentationError` in `opscore/api.py` and `opscore/storage.py`. These were leftover markers from previous `apply_diff` operations.
    *   **Diagnosis:** Used `read_file` to inspect the problematic lines and confirm the presence of leftover markers (`:start_line:`, `-------`, `=======`).
    *   **Resolution:** Used `apply_diff` and `write_to_file` to remove the markers and correct indentation in `opscore/api.py` and `opscore/storage.py`.
    *   **Verification:** `docker logs opscore_service_real` showed the Ops-Core service starting without syntax errors.

3.  **Basic Ops-Core/AgentKit Integration Test Failure:**
    *   **Issue:** The real AgentKit integration test (`tests/integration/test_real_agentkit_workflow.py`) failed because Ops-Core returned 404 Not Found when polling for agent state.
    *   **Diagnosis:** Checked Ops-Core container logs. Saw that the `/v1/opscore/internal/agent/notify` endpoint was reached (200 OK), but no logs indicated agent registration was processed. Realized the registration logic in `opscore/api.py` was commented out from a previous minimal test.
    *   **Resolution:** Uncommented the agent registration logic within the `agent_notification` function in `opscore/api.py`.
    *   **Verification:** The real AgentKit integration test (`tests/integration/test_real_agentkit_workflow.py`) passed successfully, confirming basic integration and registration are working outside of load testing.

**Current Load Testing Debugging Status:**

*   **Issue:** Running the Scenario 1 load test still results in 401 Unauthorized errors for state update and polling requests.
*   **Diagnosis:** Added debug logging in the Locust `on_start` method to print headers after restoration. Log output showed the `Authorization` header was missing. Realized that restoring `original_headers` (captured before Locust sets default headers) was overwriting the necessary `Authorization` header.
*   **Resolution Attempted:** Attempted to explicitly add the `Authorization` header after restoring `original_headers` in `on_start`.
*   **Current Blocker:** The load test still fails with 401 Unauthorized errors, and the debug logs indicate the `Authorization` header is still not being correctly applied to the `self.client` headers for the polling requests within `on_start`.

**Next Steps:**

1.  Investigate why the explicit addition of the `Authorization` header in the Locust `on_start` method is not persisting for subsequent requests made by `self.client` within that method's polling loop.
2.  Once the API key is confirmed to be sent with polling requests, re-run the load test to see if the 401 errors are resolved.
3.  If 401 errors persist, investigate the API key verification logic in Ops-Core (`opscore/api.py:verify_api_key`) under load.
4.  If registration succeeds but other errors occur during load testing, analyze Locust and Ops-Core logs for further diagnosis.