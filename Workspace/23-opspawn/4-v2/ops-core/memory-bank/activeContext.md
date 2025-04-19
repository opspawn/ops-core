# Active Context: Ops-Core Python Module (Updated - 2025-04-19 @ 16:38)

## 1. Current Work Focus
- **Completed:** Phase 1, Phase 2, Task 3.1 (SDK), Task 3.2 (CLI), Task 3.4 (AgentKit Integration).
- **Focus:** Implementing Task 3.3 (Middleware), resolving test failures.

## 2. Recent Changes & Decisions (This Session - 2025-04-19)
- **Task 3.3 (Partially Complete): Implement Middleware:**
    - Created `opscore/middleware.py` with `RequestLoggingMiddleware` and `ErrorHandlerMiddleware`.
    - Integrated middleware into `opscore/api.py`, removing redundant exception handling from route handlers.
    - Added `get_status_code_for_exception` helper to `opscore/exceptions.py`.
    - Created `tests/test_middleware.py` with initial tests.
    - Added `pytest-httpx` and `pytest-lazy-fixture` to `requirements.txt` (later removed `pytest-lazy-fixture`).
    - Refactored tests in `tests/test_api.py`, `tests/test_storage.py`, `tests/test_lifecycle.py`, `tests/test_workflow.py`, `tests/conftest.py` to fix various errors (Pydantic validation, assertion errors, patching issues, syntax errors, fixture issues).
    - Uninstalled `pytest-lazy-fixture` due to persistent collection errors.
    - **Status:** Code implemented, but numerous test failures remain across multiple modules (`test_api`, `test_lifecycle`, `test_middleware`, `test_storage`).

## 3. Next Steps (Next Session)
- **Resolve Test Failures (Task 3.3):** Debug and fix the remaining 29 test failures and 12 errors identified in the last `pytest` run. This is the immediate priority to complete Task 3.3.
- **Refine Workflow Definition:** Define and validate the schema for `WorkflowDefinition.tasks` more strictly in `models.py`. (Deferred)
- **Refine Re-queue Logic:** Implement proper delay/backoff for re-queuing tasks when agents are busy (currently immediate re-queue). (Deferred)

## 4. Active Decisions & Considerations
- **Test Failures:** Significant number of test failures introduced or uncovered during middleware implementation and subsequent refactoring need urgent attention. Errors include `TypeError` in lifecycle tests, `AttributeError` in middleware tests, and `Failed: DID NOT RAISE` errors in storage tests.
- **Test Coverage:** Test coverage needs re-evaluation after fixing failures.
- **AgentKit Endpoint Dependency:** Webhook approach remains.
- **Integration Tests:** AgentKit integration tests (`test_agentkit_integration.py`) were skipped in the last run but previously showed `ConnectError`/`ConnectTimeout`, likely due to the Docker environment not running/accessible. Needs verification after unit tests pass.
- **Error Handling:** Middleware now centralizes error handling, but underlying issues exposed in tests need fixing.

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
- Learned nuances of testing async fixtures with `pytest-asyncio` and `pytest-httpx`, requiring specific fixture patterns to avoid `AttributeError` and cleanup warnings.
- Learned correct usage of `click.testing.CliRunner` for capturing `stderr` (`mix_stderr=False` during initialization).
- Ensured tests explicitly handle environment variables to avoid interference from the external shell environment.