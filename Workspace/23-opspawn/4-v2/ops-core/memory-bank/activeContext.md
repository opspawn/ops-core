# Active Context: Ops-Core Python Module (Updated - 2025-04-19 @ 21:51)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration).
- **Focus:** Implementing Task 3.3 (Middleware), resolving test failures.

## 2. Recent Changes & Decisions (This Session - 2025-04-19 16:43 - 21:51)
- **Task 3.3 (Partially Complete): Implement Middleware:**
    - Created `opscore/middleware.py` with `RequestLoggingMiddleware` and `ErrorHandlerMiddleware`.
    - Integrated middleware into `opscore/api.py`, removing redundant exception handling from route handlers.
    - Added `get_status_code_for_exception` helper to `opscore/exceptions.py`.
    - Created `tests/test_middleware.py` with initial tests.
    - Added `pytest-httpx` and `pytest-lazy-fixture` to `requirements.txt` (later removed `pytest-lazy-fixture`).
    - Refactored tests in `tests/test_api.py`, `tests/test_storage.py`, `tests/test_lifecycle.py`, `tests/test_workflow.py`, `tests/conftest.py` to fix various errors (Pydantic validation, assertion errors, patching issues, syntax errors, fixture issues). (Previous Session)
    - Uninstalled `pytest-lazy-fixture` due to persistent collection errors. (Previous Session)
    - **Debugged Test Failures (Task 3.3):**
        - Added `test_client` fixture to `tests/conftest.py`.
        - Fixed local `test_client` fixture definition and usage in `tests/test_middleware.py`.
        - Corrected middleware order and assertions in `tests/test_middleware.py`.
        - Corrected argument passing (`agent_id`, `details`) in `tests/test_lifecycle.py` test setup.
        - Corrected exception handling/mocking/assertions for storage errors in `tests/test_lifecycle.py`.
        - Added generic exception wrapping to storage functions in `opscore/storage.py` to catch lock errors.
    - **Status:** Task 3.3 is partially complete. Test failures reduced from 31 to 8. Remaining failures are in `test_agentkit_integration.py` (2), `test_api.py` (1), and `test_storage.py` (5).

## 3. Next Steps (Next Session)
- **Resolve Remaining Test Failures (Task 3.3):** Debug and fix the remaining 8 test failures (2 integration, 1 API, 5 storage) to fully complete Task 3.3.
- **Refine Workflow Definition:** Define and validate the schema for `WorkflowDefinition.tasks` more strictly in `models.py`. (Deferred)
- **Refine Re-queue Logic:** Implement proper delay/backoff for re-queuing tasks when agents are busy (currently immediate re-queue). (Deferred)

## 4. Active Decisions & Considerations
- **Test Failures:** 8 test failures remain for Task 3.3.
    - `test_agentkit_integration.py` (2): `ConnectError` - likely Docker/network issue, deferred.
    - `test_api.py` (1): `AssertionError` in `test_trigger_workflow_success_with_inline_def` (mock not called).
    - `test_storage.py` (5): `Failed: DID NOT RAISE StorageError` - error handling within storage functions needs further review despite recent fixes.
- **Test Coverage:** Test coverage needs re-evaluation after fixing remaining failures.
- **AgentKit Endpoint Dependency:** Webhook approach remains.
- **Integration Tests:** `test_agentkit_integration.py` failures need investigation, potentially requiring the Docker environment to be running.
- **Error Handling:** Middleware is functional, but the remaining `DID NOT RAISE` errors in `test_storage.py` indicate potential gaps in how storage exceptions are handled or tested.

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