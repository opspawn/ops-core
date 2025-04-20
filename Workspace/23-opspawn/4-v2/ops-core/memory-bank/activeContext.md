# Active Context: Ops-Core Python Module (Updated - 2025-04-20 @ 15:49)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration), Task 3.3 (Middleware), Task 5.6 (AgentKit Requirements Doc Update).
- **Focus:** Task 4.2 (Real AgentKit Integration Tests) - Partially complete. Fixed original 500 error, now blocked by agent registration/discovery issue (test times out receiving 404s).

## 2. Recent Changes & Decisions (This Session - 2025-04-20 15:06 - 15:49)
- **Debug Task 4.2 (500 Error):**
    - Attempted running test via `docker-compose run`, failed due to `docker-compose` not being available inside the container (`FileNotFoundError`). Commented out problematic `docker_compose_up_down` fixture in `test_real_agentkit_workflow.py`.
    - Attempted running test via `docker-compose run` again, failed due to DNS resolution error (`Temporary failure in name resolution`) when test tried accessing `http://opscore:8000`.
    - Switched strategy: Ran services via `docker-compose up -d` and ran `pytest` from host.
    - Successfully reproduced the 500 Internal Server Error on `GET /v1/opscore/agent/{agent_id}/state`.
    - Analyzed Ops-Core logs (`opscore_error_logs.txt`) and identified the root cause: `AttributeError: 'NoneType' object has no attribute 'state'` in `opscore/api.py` line 192. This occurred because `lifecycle.get_state` returned `None` (as no state was found for the requested agent ID), but the API endpoint didn't handle this `None` case before trying to access `.state`.
    - Fixed the error by uncommenting the check for `agent_state is None` in `opscore/api.py:get_agent_state` and raising an `HTTPException(404)` in that case.
- **Task 4.2 (New Blocker):**
    - Re-ran the integration test after fixing the 500 error.
    - The test now fails with a `TimeoutError` because the `poll_for_agent_state` helper function receives repeated 404 Not Found errors when checking for the agent's state after startup.
    - Analysis of Ops-Core logs (`opscore_registration_logs.txt`) confirmed that the agent ID registered via the AgentKit webhook (e.g., `39a97542-985f-4a8a-89f4-ede564f64573`) did not match the ID the test was initially configured to poll (`test-sim-agent-001`).
    - Temporarily hardcoded the observed registered ID into the test file (`test_real_agentkit_workflow.py`) for debugging.
    - Re-ran the test with the hardcoded ID. It still failed with a timeout, receiving only 404s. This indicates the agent registration via the webhook is not being successfully processed and stored by Ops-Core within the test's timeout period, even when polling for the correct ID.

## 3. Next Steps (Next Session)
- **Debug Task 4.2 (Registration):** Investigate why the agent registration, triggered by the AgentKit webhook (`POST /v1/opscore/internal/agent/notify`), is not resulting in the agent being found via the `GET /v1/opscore/agent/{agent_id}/state` endpoint within the test timeout. Examine logs from Ops-Core, AgentKit, and the Simulated Agent during startup. Verify webhook delivery and processing.
- **Complete Task 4.2:** Once the registration issue is resolved, re-run integration tests and ensure the full end-to-end workflow passes.
- **Address `httpx` Warnings:** Eventually address Task B7 related to `TestClient` instantiation in `tests/test_middleware.py`.
- **Consult `TASK.md`:** Identify next tasks after 4.2 (likely Task 4.3: CI/CD setup).

## 4. Active Decisions & Considerations
- Using separate `docker-compose.real-agentkit.yml` for real integration tests.
- Running integration tests from the host machine against services started with `docker-compose up -d` is more reliable than using `docker-compose run`.
- AgentKit fixes for Issue #1 are available on branch `feature/issue-1-ops-core-integration-fixes`.
- The original 500 error in `GET /state` was due to improper handling of `None` return from `lifecycle.get_state`. This is now fixed.
- **Current Blocker:** The integration test times out waiting for the agent to appear in Ops-Core state after the registration webhook, receiving only 404s. This points to an issue in the registration/webhook processing or storage access timing.

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