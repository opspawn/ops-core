# Debugging Plan: Task 3.3 Middleware Test Failures

**Date:** 2025-04-19

**Objective:** Resolve the 29 test failures and 12 errors reported after implementing the logging and error handling middleware (Task 3.3).

**Context:**
*   Middleware (`opscore/middleware.py`) was added.
*   Related modules (`opscore/api.py`, `opscore/exceptions.py`) and tests (`tests/test_api.py`, `tests/test_lifecycle.py`, `tests/test_middleware.py`, `tests/test_storage.py`, `tests/conftest.py`) were refactored.
*   This introduced significant test issues: 29 failures, 12 errors.
*   Known error types: `TypeError` (lifecycle), `AttributeError` (middleware), `Failed: DID NOT RAISE` (storage).

**Debugging Strategy:**

1.  **Detailed Failure Analysis:**
    *   Run `pytest -v` in debug/code mode to capture full tracebacks.
    *   Prioritize analyzing the 12 **errors** first.

2.  **Targeted Investigation based on Error Types:**
    *   **`TypeError` in `tests/test_lifecycle.py`:** Investigate data type mismatches between API, middleware, lifecycle, and storage. Check Pydantic models and data transformations.
    *   **`AttributeError` in `tests/test_middleware.py`:** Examine test setup, mocks, and fixtures (`conftest.py`, `test_middleware.py`). Verify `request`/`response` object attributes/methods when interacting with middleware.
    *   **`Failed: DID NOT RAISE` in `tests/test_storage.py` (and others):** Analyze how `ErrorHandlerMiddleware` intercepts exceptions. Tests expecting specific `OpsCoreError` subtypes might now receive HTTP errors. Adjust tests or refine middleware/exception mapping (`exceptions.py:get_status_code_for_exception`).

3.  **Review Recent Changes:**
    *   Systematically review code modified during Task 3.3:
        *   `opscore/middleware.py`
        *   `opscore/api.py`
        *   `opscore/exceptions.py`
        *   `tests/conftest.py`
        *   Affected test files (`test_api.py`, `test_lifecycle.py`, etc.)

4.  **Incremental Fixes and Testing:**
    *   Apply fixes incrementally, focusing on one error type/module at a time.
    *   Run `pytest` frequently to check fixes and prevent regressions.

**Next Steps:**
*   Switch to 'debug' mode.
*   Execute the plan starting with Step 1 (running `pytest -v`).