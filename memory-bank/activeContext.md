# Active Context: Ops-Core Python Module (Updated - 2025-04-20 @ 20:29)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update), **Task 4.2 (Real AgentKit Integration Tests)**, **Task 4.4 (Minimal Load Test Scenario 0)**.
- **Focus:** Debugging agent registration failures during load testing (Scenario 1 and 2).

## 2. Recent Changes & Decisions (This Session - 2025-04-21 @ 08:50 - 09:23)
- **Completed Task 4.4 (Minimal Load Test Scenario 0):**
    - Added Scenario 0 (Minimal Load Test) to `load_testing_plan.md`.
    - Created `load_tests/opscore_locustfile.py` to implement load tests using Locust.
    - Debugged Locust execution issues:
    - Resolved "command not found" by executing Locust via the virtual environment's Python interpreter (`./.venv/bin/python -m locust`).
    - Resolved `AttributeError: 'OpsCoreUser' object has no attribute 'get_request_meta'` by removing incorrect method calls in `load_tests/opscore_locustfile.py`.
    - Resolved `401 Unauthorized` error by ensuring the correct API key ("test-api-key") was passed as an environment variable to the Locust command.
    - Resolved `404 Not Found` error for state updates by adding agent registration via the internal notification endpoint (`/v1/opscore/internal/agent/notify`) in `load_tests/opscore_locustfile.py`'s `on_start` method.
    - Configured Locust to run in headless mode and redirect output to `load_test_results.txt` for easier review.
    - Successfully executed the minimal load test (Scenario 0) with 0% failures.
- **Debugging Agent Registration Failures (Scenario 1 & 2):**
    - Observed 100% failures in Scenario 1 and 2 load tests related to agent registration (`Failed to register agent: 0`, `ConnectionResetError`).
    - Removed `Authorization` header for registration endpoint calls in `load_tests/scenario_1/locustfile.py` as it's not required. This did not resolve the issue.
    - Identified `AttributeError: 'NoneType' object has no attribute 'state'` in Ops-Core logs, indicating an issue when getting agent state before it's set. Fixed this in `opscore/api.py`. This prevented the 500 error but not the registration failure.
    - Added a small delay after registration in `load_tests/scenario_1/locustfile.py` to allow state to be saved. This did not resolve the issue.
- **Decision:** Use headless mode and output redirection for future load test runs.
- **Decision:** Shorten test duration during debugging cycles.

## 3. Next Steps (Next Session)
- **Continue Debugging Agent Registration:** Investigate the root cause of agent registration failures (`Failed to register agent: 0`, `ConnectionResetError`) during load testing. Focus on the `/v1/opscore/internal/agent/notify` endpoint and its interaction with the storage layer.
- **Execute Remaining Load Tests (if registration is fixed):** If agent registration is resolved, execute the full load testing scenarios (Scenario 1, 2, 3, and 4) as defined in `load_testing_plan.md`.
- **Analyze Results:** Review the output from the load tests in `load_test_results.txt` and potentially other monitoring tools (`docker stats`).
- **Document Findings:** Summarize the results, identify bottlenecks, and document recommendations in `load_testing_plan.md` and potentially other documentation.
- **Address Backlog Items:**
    - **Task B8:** Implement proper environment variable loading in test suite to remove hardcoded API key.
    - **Task B9:** Investigate more robust test verification methods (alternatives to API polling).
    - **Task B7:** Address `httpx` DeprecationWarnings.

## 4. Active Decisions & Considerations
- Using Redis storage backend for the integration test environment (`docker-compose.real-agentkit.yml`).
- Ops-Core storage interaction layer (`storage.py`, `lifecycle.py`, `api.py`) is asynchronous.
- API key authentication uses the `Authorization: Bearer <key>` header format.
- Tests must be run using the virtual environment's Python interpreter (`./.venv/bin/python -m pytest ...` or `./.venv/bin/python -m locust ...`).
- Load test results will be output to `load_test_results.txt`.
- The API key "test-api-key" is used for load testing against the Docker environment.

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
- API authentication details (header format, key source) must match between the client (test fixture) and the server (API dependency).
- Interrupted `write_to_file` operations revert the file, requiring the operation to be retried.
- Careful code modification and verification (e.g., indentation, placement within functions) are crucial, especially when using `apply_diff`.
- API schema validation errors (like 422) require checking the exact payload being sent against the API's expectations.
- Race conditions in asynchronous tests can sometimes be mitigated by adjusting polling intervals or changing the verification strategy (e.g., waiting for a stable state instead of a transient one).
- **New Insight:** When load testing an API that requires agent registration, ensure the load test script includes the registration step before attempting other agent-specific operations.
- **New Insight:** Using Locust's headless mode with output redirection is effective for running tests from the command line and reviewing results in a file.
- **New Insight:** Verify the API key expected by the target service (e.g., from `.env` or Docker Compose config) matches the key used by the load test client.
- **New Insight:** Ensure Docker Compose services are running correctly before executing tests that depend on them. Use `docker compose up -d` and check container status if needed.

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