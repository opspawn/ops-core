# Active Context: Ops-Core Python Module (Updated - 2025-04-20 @ 19:20)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update).
- **Focus:** Task 4.2 (Real AgentKit Integration Tests) - Partially complete. Implemented Redis storage backend and refactored related code. Test now fails with `401 Unauthorized` when polling Ops-Core API for agent state.

## 2. Recent Changes & Decisions (This Session - 2025-04-20 @ 19:20 - [Current Time])
- **Debug Task 4.2 (Real AgentKit Integration Tests):**
    - Continued debugging the integration test `tests/integration/test_real_agentkit_workflow.py`.
    - Resolved `SyntaxError` and `ValueError` in `tests/conftest.py` related to duplicated code and async fixture handling.
    - Identified that the `opscore_client` fixture was using a default API key because the `OPSCORE_API_KEY` environment variable was not correctly loaded in the test environment.
    - Attempted to load `.env` using `python-dotenv`, but encountered issues with the environment variable not being picked up.
    - **Decision:** Temporarily hardcoded the `OPSCORE_API_KEY` ("test-api-key") directly into the `opscore_client` fixture in `tests/conftest.py` to unblock debugging of the test workflow. This is a temporary workaround; the `.env` loading issue needs to be addressed later (Task B?).
    - **Current Status:** The `401 Unauthorized` error is resolved. The integration test now proceeds further but fails with a `TimeoutError` waiting for the agent state to become 'UNKNOWN' via the Ops-Core API.

## 3. Next Steps (Next Session)
- **Debug Task 4.2 (UNKNOWN State Timeout):** Continue debugging why the integration test times out waiting for the `UNKNOWN` state to appear via the Ops-Core API. This might involve:
    - Analyzing Ops-Core logs for the webhook processing (`/v1/opscore/internal/agent/notify`) and state retrieval (`/v1/opscore/agent/{agentId}/state`) endpoints to see if the webhook is received and processed correctly and if the state is being written to Redis.
    - Checking the Redis database directly to see if the `UNKNOWN` state is being written correctly by the webhook handler.
    - Reviewing the timing and logic in `opscore/lifecycle.py` and `opscore/storage.py` related to agent registration and state updates.
    - Verifying the simulated agent is correctly sending the registration webhook to Ops-Core.
- **Complete Task 4.2:** Once the `UNKNOWN` and subsequent `idle` states are correctly verified, ensure the full end-to-end workflow passes.
- **Address `.env` Loading Issue:** Investigate and fix why `python-dotenv` is not correctly loading environment variables in the test environment (Create a new backlog task for this, e.g., Task B8).
- **Address `httpx` Warnings:** Eventually address Task B7 related to `TestClient` instantiation in `tests/test_middleware.py`.
- **Consult `TASK.md`:** Identify next tasks after 4.2 (likely Task 4.3: CI/CD setup).

## 4. Active Decisions & Considerations
- Using Redis storage backend for the integration test environment (`docker-compose.real-agentkit.yml`).
- Ops-Core storage interaction layer (`storage.py`, `lifecycle.py`, `api.py`) refactored to be asynchronous.
- Integration test polls the Ops-Core API (`/v1/opscore/agent/{agentId}/state`) for state verification.
- API key authentication uses the `Authorization: Bearer <key>` header format.
- Tests must be run using the virtual environment's Python interpreter (`./.venv/bin/python -m pytest ...`).
- **Current Blocker:** Integration test fails with `TimeoutError` waiting for the 'UNKNOWN' state after the agent registers. The `401 Unauthorized` error is temporarily bypassed by hardcoding the API key in the test fixture.

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