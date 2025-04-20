# Active Context: Ops-Core Python Module (Updated - 2025-04-20 @ 16:38)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update).
- **Focus:** Task 4.2 (Real AgentKit Integration Tests) - Partially complete. Fixed original 500 error, addressed test fixture usage, updated agent ID discovery, but still blocked by a storage/timing issue.

## 2. Recent Changes & Decisions (This Session - 2025-04-20 16:38 - 17:06)
- **Debug Task 4.2 (Test Fixture Usage & Agent Discovery):**
    - Continued debugging the `TimeoutError` in `test_real_agentkit_workflow.py`.
    - Resolved `AttributeError: 'async_generator' object has no attribute 'get'` by correctly using `@pytest_asyncio.fixture` and changing fixture scope to `function`.
    - Identified that the test was incorrectly trying to discover the dynamic agent ID from AgentKit's `/v1/agents` endpoint (which returned 404).
    - Modified the test to get the dynamic agent ID from the Simulated Agent's `/health` endpoint, which now returns the AgentKit-assigned ID after registration.
    - Updated the Simulated Agent code (`tests/simulated_agent/main.py`) to store and return the actual AgentKit-assigned ID from its `/health` endpoint.
    - Added a 5-second `asyncio.sleep` in the test after discovering the agent ID to allow Ops-Core time to process the registration webhook.
    - Despite these changes, the test still fails with a `TimeoutError` while polling Ops-Core for the initial `UNKNOWN` state, receiving repeated `404 Not Found` responses from Ops-Core.
    - Examined Ops-Core logs (`docker logs opscore_service_real`) which confirm the webhook is received and processed, and `lifecycle.register_agent` and `lifecycle.set_state("UNKNOWN")` are called. However, subsequent `read_latest_agent_state` calls from the test's polling logic return `None`, leading to the 404s.
    - Identified the current blocker as a potential storage/timing issue within the in-memory storage implementation (`opscore/storage.py`), where the state saved by the webhook processing thread/context is not immediately available or visible to the test's polling thread/context.
    - Removed `autouse=True` from the `clear_storage_before_each_test` fixture in `tests/conftest.py` to prevent it from clearing the storage before the integration test runs, which was a potential cause of the state not being found.

## 3. Next Steps (Next Session)
- **Debug Task 4.2 (Storage/Timing Issue):** Investigate and fix the issue in `opscore/storage.py` or the test timing that prevents the test from reading the agent state immediately after webhook processing. This might involve further adjustments to the test's polling logic or examining the thread safety/visibility of the in-memory storage.
- **Complete Task 4.2:** Once the initial "UNKNOWN" state is successfully verified, ensure the full end-to-end workflow (triggering workflow, agent state transitions to "active" and "idle") passes.
- **Address `httpx` Warnings:** Eventually address Task B7 related to `TestClient` instantiation in `tests/test_middleware.py`.
- **Consult `TASK.md`:** Identify next tasks after 4.2 (likely Task 4.3: CI/CD setup).

## 4. Active Decisions & Considerations
- Using separate `docker-compose.real-agentkit.yml` for real integration tests.
- Running integration tests from the host machine against services started with `docker compose up -d` is more reliable than using `docker compose run`.
- AgentKit fixes for Issue #1 are available on branch `feature/issue-1-ops-core-integration-fixes`.
- The original 500 error in `GET /state` was due to improper handling of `None` return from `lifecycle.get_state`. This is now fixed.
- **Current Blocker:** The integration test fails with a `TimeoutError` because Ops-Core returns 404 for the agent state, likely due to a storage/timing issue preventing the test's polling from seeing the state saved by the webhook.
- The Docker daemon is currently running directly (`sudo dockerd -H unix:///var/run/docker.sock`) as a workaround for the systemd socket activation issue on WSL. This needs to be resolved for a robust setup, but the current focus is on the integration test.
- Removed `autouse=True` from `clear_storage_before_each_test` to prevent it from interfering with the integration test's state verification.

## 5. Important Patterns & Preferences
- Continue following Python best practices (PEP8, type hints).
- Use FastAPI conventions.
- Maintain modularity.
- Ensure comprehensive logging.
- Write unit tests for new logic and improve coverage for existing logic.
- Use timezone-aware datetimes (`datetime.now(timezone.utc)`).
- Use custom exceptions derived from `OpsCoreError` for specific error conditions.

## 6. Learnings & Project Insights
- Core lifecycle and workflow functions are implemented with initial test coverage.
- API endpoints for core interactions are defined.
- Refactoring storage and lifecycle layers to use Pydantic models improved consistency.
- Careful attention to dependencies (like `pytest-cov`) and virtual environments is crucial.
- Mocking and async testing patterns established.
- Using `asyncio.to_thread` to bridge async/sync code where necessary (e.g., `process_next_task` calling `lifecycle.get_state`).
- Custom exception hierarchy established for more specific error handling.
- Refactored integration tests to use `pytest-asyncio` and `httpx`.
- Implemented webhook pattern for inter-service communication (mock AgentKit -> Ops-Core).
- Debugging integration tests highlighted the importance of running tests within the correct Docker network context.
- Resolved chained errors involving indentation, type errors, missing exceptions, and incorrect exception handling logic (Previous Session).
- Learned nuances of testing async fixtures with `pytest-asyncio` and `pytest-httpx`, requiring specific fixture patterns (`async with`/`yield`) and careful naming to avoid conflicts (`local_middleware_client`).
- Learned correct usage of `click.testing.CliRunner` for capturing `stderr` (`mix_stderr=False` during initialization).
- Ensured tests explicitly handle environment variables to avoid interference from the external shell environment.
- Corrected test setup logic involving function argument mismatches (`register_agent`).
- Refined exception handling in storage layer to wrap generic exceptions occurring during lock acquisition or internal operations.
- Adjusted test assertions to match actual exception messages wrapped by higher layers.
- Debugging real AgentKit integration revealed issues with health checks, webhook serialization (fixed in AgentKit branch), and Ops-Core state retrieval (500 error fixed, now 404/timeout).
- Confirmed need for API key authentication on Ops-Core `GET /state` endpoint.
- API endpoints should gracefully handle cases where underlying functions (like `lifecycle.get_state`) return `None`, typically by returning appropriate HTTP status codes (e.g., 404).
- Docker environment issues on WSL (systemd socket activation, docker-compose version incompatibility) can block development and require system-level troubleshooting. Using `docker compose` (v2) is necessary with newer Docker Engine versions.
- The integration test was failing due to polling for a stale/incorrect dynamically generated agent ID. The test needs to discover the actual ID from AgentKit after registration.
- Incorrect usage of pytest async fixtures (`async_generator` vs `httpx.AsyncClient` instance) caused an `AttributeError` when attempting to use the client.