# Active Context: Ops-Core Python Module (Updated - 2025-04-20 @ 19:20)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update).
- **Focus:** Task 4.2 (Real AgentKit Integration Tests) - Partially complete. Implemented Redis storage backend and refactored related code. Test now fails with `401 Unauthorized` when polling Ops-Core API for agent state.

## 2. Recent Changes & Decisions (This Session - 2025-04-20 18:56 - 19:20)
- **Debug Task 4.2 (Idle State Update / 401 Error):**
    - Attempted to run integration test `tests/integration/test_real_agentkit_workflow.py` to gather logs.
    - Switched from `architect` to `code` mode to allow command execution.
    - Test failed, revealing that the test was polling storage directly (`get_storage()`) from the host, not using Redis.
    - Modified `tests/integration/test_real_agentkit_workflow.py` to poll the Ops-Core API (`/v1/opscore/agent/{agentId}/state`) instead of storage directly.
    - Test failed again with `401 Unauthorized`, indicating an API key authentication issue.
    - Identified that the test was likely running outside the virtual environment.
    - Attempted to run the test using `source ./.venv/bin/activate`, but failed with `ModuleNotFoundError: No module named 'redis'`.
    - Confirmed `redis` package was missing from the venv using `pip list`.
    - Installed `redis` package into the venv using `./.venv/bin/pip install redis`.
    - Attempted to run the test using `./.venv/bin/python -m pytest`, but failed with `NameError: name 'httpx' is not defined` in `tests/conftest.py`.
    - Added `import httpx` to `tests/conftest.py`.
    - Re-ran test using `./.venv/bin/python -m pytest`. Test still failed with `401 Unauthorized`.
    - Identified that the `opscore_client` fixture in `tests/conftest.py` was sending the API key in the wrong header (`X-API-Key` instead of `Authorization: Bearer`).
    - Attempted to correct the header format in `tests/conftest.py` using `write_to_file`, but the operation was interrupted and reverted.
    - **Current Status:** Integration test `test_real_agentkit_workflow.py` fails with `401 Unauthorized` when polling the Ops-Core API for agent state. The fix to the `opscore_client` fixture in `tests/conftest.py` to send the correct `Authorization: Bearer` header needs to be re-applied.

## 3. Next Steps (Next Session)
- **Fix Task 4.2 (401 Unauthorized):**
    - Re-apply the fix to the `opscore_client` fixture in `tests/conftest.py` to ensure the `Authorization: Bearer <key>` header is correctly sent, using the API key from the `OPSCORE_API_KEY` environment variable. Include the print statement for verification.
    - Re-run the integration test (`./.venv/bin/python -m pytest tests/integration/test_real_agentkit_workflow.py`) to confirm the 401 error is resolved.
- **Debug Task 4.2 (Idle State Update):** Once the 401 error is fixed, continue debugging why the test times out waiting for the `UNKNOWN` state (and subsequently the `idle` state) to appear via the API. This might involve:
    - Analyzing Ops-Core logs for the webhook processing (`/v1/opscore/internal/agent/notify`) and state retrieval (`/v1/opscore/agent/{agentId}/state`) endpoints.
    - Checking Redis directly to see if the `UNKNOWN` state is being written correctly by the webhook handler.
    - Reviewing the timing and logic in `opscore/lifecycle.py` and `opscore/storage.py` related to agent registration and state updates.
- **Complete Task 4.2:** Once the `idle` state is correctly verified, ensure the full end-to-end workflow passes.
- **Address `httpx` Warnings:** Eventually address Task B7 related to `TestClient` instantiation in `tests/test_middleware.py`.
- **Consult `TASK.md`:** Identify next tasks after 4.2 (likely Task 4.3: CI/CD setup).

## 4. Active Decisions & Considerations
- Using Redis storage backend for the integration test environment (`docker-compose.real-agentkit.yml`).
- Ops-Core storage interaction layer (`storage.py`, `lifecycle.py`, `api.py`) refactored to be asynchronous.
- Integration test polls the Ops-Core API (`/v1/opscore/agent/{agentId}/state`) for state verification.
- API key authentication uses the `Authorization: Bearer <key>` header format.
- Tests must be run using the virtual environment's Python interpreter (`./.venv/bin/python -m pytest ...`).
- **Current Blocker:** Integration test fails with `401 Unauthorized` due to the test client fixture (`opscore_client`) not sending the correct API key header format (fix was interrupted).

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