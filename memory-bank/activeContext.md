# Active Context: Ops-Core Python Module (Updated - 2025-04-21 @ 23:59)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update), **Task 4.2 (Real AgentKit Integration Tests)**, **Task 4.4 (Minimal Load Test Scenario 0 & Scenario 1)**.
- **Focus:** Debugging 500 errors during Scenario 2 load testing (Task 4.4).

## 2. Recent Changes & Decisions (This Session - 2025-04-21 @ 10:38 - 23:59)
- **Continued Debugging Task 4.4 (Load Testing - Scenario 2):**
    - Implemented agent registration in `load_tests/scenario_2/locustfile.py` based on Scenario 1's working script.
    - Iteratively debugged header handling and payload issues in the Scenario 2 script, resolving initial 401 and 422 errors.
    - Identified persistent 500 Internal Server Errors on the workflow initiation endpoint (`POST /v1/opscore/agent/{agentId}/workflow`).
    - Analysis of Ops-Core logs revealed a `NameError: name '_workflow_definitions' is not defined` in `opscore/storage.py`, indicating the workflow definition was not being loaded or accessed correctly.
    - Added a FastAPI startup event in `opscore/api.py` to load the `docs/sample_workflow.json` definition into storage.
    - Modified `opscore/storage.py` to use a global storage instance (InMemory or Redis based on env var) instead of creating a new instance per `get_storage()` call, aiming to fix the `NameError`.
    - **Current Status:** The `NameError` persists in the latest test run, suggesting the global storage fix was ineffective or incomplete. The root cause of the workflow definition not being found by the API endpoint needs further investigation.

## 3. Next Steps (Next Session)
- **Further Debug Scenario 2 Workflow Trigger:** Investigate why the `NameError` persists despite the global storage instance. This may involve examining how the storage instance is accessed and used in `opscore/api.py` and `opscore/storage.py` more closely, particularly around the `read_workflow_definition` call.
- **Verify Workflow Definition Loading:** Add explicit logging in `opscore/api.py`'s startup event and in `opscore/storage.py`'s `save_workflow_definition` and `read_workflow_definition` to confirm the workflow is being loaded and stored correctly and accessed with the expected ID.
- **Re-run Short Scenario 2 Test:** After adding logging, run the short test again and analyze the new logs for clues.
- **Address Root Cause:** Based on log analysis, identify and fix the root cause of the `NameError`.
- **Verify Scenario 2 Fix:** Run a short (e.g., 30-second) test for Scenario 2 to confirm the 500 errors are resolved.
- **Execute Full Scenario 2 Load Test:** If the short run is successful, execute the full 18-minute Scenario 2 run, attempting to save output to a file again.
- **Execute Remaining Load Tests:** Proceed with Scenarios 3 and 4 as outlined in `load_testing_plan.md`, saving output to files where possible.
- **Analyze Results:** Compile and analyze the collected metrics from all scenarios.
- **Document Findings:** Summarize the results, identify bottlenecks, and document recommendations in `docs/load_testing_findings.md` and update `load_testing_plan.md`.
- **Address Backlog Items:** Continue addressing items in the Backlog section of `TASK.md` as appropriate.

## 4. Active Decisions & Considerations
- Using Redis storage backend for the integration test environment (`docker-compose.real-agentkit.yml`).
- Ops-Core storage interaction layer (`storage.py`, `lifecycle.py`, `api.py`) is asynchronous.
- API key authentication uses the `Authorization: Bearer <key>` header format.
- Tests must be run using the virtual environment's Python interpreter (`./.venv/bin/python -m pytest ...` or `./.venv/bin/m locust ...`).
- Load test results for full runs should ideally be output to files (e.g., `load_test_results_scenarioX_full.txt`), although redirection issues were encountered.
- The API key "test-api-key" is used for load testing against the Docker environment.
- Agent registration is a prerequisite for triggering workflows for a specific agent ID.
- The `NameError: name '_workflow_definitions' is not defined` in `opscore/storage.py` during workflow trigger indicates a problem with accessing the loaded workflow definition.
- The storage subsystem (`opscore/storage.py`) now uses a global instance (`storage_instance`) initialized based on `OPSCORE_STORAGE_TYPE`.

## 5. Important Patterns & Preferences
- Continue following Python best practices (PEP8, type hints).
- Use FastAPI conventions.
- Maintain modularity.
- Ensure comprehensive logging.
- Write unit tests for new logic and improve coverage for existing logic.
- Use timezone-aware datetimes (`datetime.now(timezone.utc)`).
- Use custom exceptions derived from `OpsCoreError` for specific error conditions.
- Use `async`/`await` for I/O bound operations, especially storage interactions.
- Ensure tests run within the correct virtual environment.

## 6. Learnings & Project Insights
- Implementing a new storage backend requires careful consideration of configuration (Docker, env vars), dependencies, and abstraction layers (`get_storage`).
- Refactoring synchronous code to asynchronous (`async`/`await`) requires propagating changes up the call stack (storage -> lifecycle -> api).
- Integration testing complex interactions between multiple services (Ops-Core, AgentKit, Agent, Redis) can reveal subtle timing issues and race conditions.
- Direct storage polling in tests can bypass API-level issues but might hide problems that would occur in real usage. It can also lead to environment mismatches if not carefully managed.
- Need to ensure components (like the simulated agent) handle potential failures during initial setup (like state reporting) gracefully, possibly with retry logic.
- Debugging requires analyzing logs from multiple services involved in the interaction.
- Environment variable scope is important (container vs. host test process). Test fixtures need access to the correct environment variables (e.g., API keys).
- Ensuring tests run within the correct virtual environment is crucial for accessing installed dependencies (`./.venv/bin/python -m pytest ...` is more reliable than `source activate && pytest ...`).
- API authentication details (header format, key source) must match between the client (test fixture) and the server (API dependency).
- Interrupted `write_to_file` operations revert the file, requiring the operation to be retried.
- Careful code modification and verification (e.g., indentation, placement within functions) are crucial, especially when using `apply_diff`.
- API schema validation errors (like 422) require checking the exact payload being sent against the API's expectations.
- Race conditions in asynchronous tests can sometimes be mitigated by adjusting polling intervals or changing the verification strategy (e.g., waiting for a stable state instead of a transient one).
- **New Insight:** When load testing an API that requires agent registration, ensure the load test script includes the registration step before attempting other agent-specific operations.
- **New Insight:** Using Locust's headless mode with output redirection is effective for running tests from the command line and reviewing results in a file, although specific command syntax may vary and require testing.
- **New Insight:** Verify the API key expected by the target service (e.g., from `.env` or Docker Compose config) matches the key used by the load test client.
- **New Insight:** Ensure Docker Compose services are running correctly before executing tests that depend on them. Use `docker compose up -d` and check container status if needed.
- **New Insight:** 100% 500 errors on the workflow endpoint in Scenario 2 were likely caused by attempting to trigger workflows for agents that were not registered by the Locust user instance. Agent registration needs to be added to the Scenario 2 Locust script's `on_start`.
- **New Insight:** When load testing an API that requires agent registration, ensure the load test script includes the registration step before attempting other agent-specific operations.
- **New Insight:** Using Locust's headless mode with output redirection is effective for running tests from the command line and reviewing results in a file.
- **New Insight:** Verify the API key expected by the target service (e.g., from `.env` or Docker Compose config) matches the key used by the load test client.
- **New Insight:** Ensure Docker Compose services are running correctly before executing tests that depend on them. Use `docker compose up -d` and check container status if needed.
- **New Insight:** The `NameError` in `storage.py` during workflow trigger suggests an issue with how workflow definitions are loaded/accessed, potentially related to storage initialization timing or scope.
- **New Insight:** Using a global storage instance in `storage.py` did not resolve the `NameError`, indicating the problem might lie in how the startup event interacts with the storage initialization or how the endpoint accesses the global instance.