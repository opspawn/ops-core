# Load Testing Debugging Summary

**Project:** Ops-Core Python Module
**Workspace Directory:** /home/sf2/Workspace/23-opspawn/4-v2/ops-core
**Task:** Task 4.4 (Performance and Load Testing) - Debugging Scenario 1 & 2

**Date:** 2025-04-21

**Summary of Debugging Efforts:**

This document summarizes the debugging steps taken during load testing of Ops-Core, focusing on resolving errors encountered in Scenario 2 (Workflow Initiation Load) and Scenario 1 (High State Update Load).

**Scenario 2 (Workflow Initiation Load) Debugging:**

*   **Initial Issue:** Scenario 2 load tests failed with 422 Unprocessable Entity errors.
*   **Finding:** The issue was identified as an incorrect payload structure being sent for workflow initiation requests.
*   **Resolution:** The payload structure in `load_tests/scenario_2/locustfile.py` was corrected.
*   **Subsequent Issues:** After fixing the payload, Scenario 2 tests failed with `ConnectionRefusedError` and 500 Internal Server Errors.
*   **Finding:** Ops-Core logs (`opscore_error_logs.txt`) showed a `NameError` in `opscore/storage.py` related to workflow definition handling, which was causing the 500 errors.
*   **Resolution:** The `NameError` in `opscore/storage.py` was fixed.
*   **Verification (Minimal Test):** A minimal Scenario 2 load test (1 user, 10 seconds) was executed with output redirected to `locust_scenario_2_output.txt`.
*   **Result:** The minimal Scenario 2 test completed without the 500 Internal Server Errors. The observed errors were `Failed to register agent` (status 0) and `ConnectionResetError`, indicating the `NameError` fix was successful for workflow initiation, but a new issue with agent registration was present.

**Scenario 1 (High State Update Load) Debugging:**

*   **Issue:** Following the minimal Scenario 2 test, Scenario 1 load tests were run and also showed 100% failures with `Failed to register agent` (status 0) and `ConnectionResetError`. This confirmed the agent registration issue was not specific to Scenario 2.
*   **Finding 1:** The `/v1/opscore/internal/agent/notify` endpoint (used for registration) does not require an API key, but the Locust user was sending an `Authorization` header. This was suspected as a potential cause for the registration failure.
*   **Resolution 1:** Modified `load_tests/scenario_1/locustfile.py` to temporarily remove the `Authorization` header before the registration call.
*   **Result 1:** Re-running the short Scenario 1 test after this change still showed 100% failures with the same registration errors. This indicated the `Authorization` header was not the primary cause.
*   **Finding 2:** Ops-Core error logs (`opscore_error_logs.txt`) showed `AttributeError: 'NoneType' object has no attribute 'state'` originating from `opscore/api.py` within the `get_agent_state` endpoint. This error occurs when `lifecycle.get_state` returns `None` (no state found for an agent), and the code attempts to access `.state`. This suggests that agents are failing to register their initial state, or the state is not immediately available after registration.
*   **Resolution 2:** Added a check for `None` in `opscore/api.py` before accessing `agent_state.state` in the debug log within `get_agent_state`. This prevents the 500 error but does not fix the underlying registration issue.
*   **Finding 3:** The persistent agent registration failures (status 0) and `ConnectionResetError` after registration, even with the `AttributeError` fixed, point to a deeper issue in the agent registration flow or the storage interaction. Although `OPSCORE_STORAGE_TYPE` is set to `redis`, the behavior suggests potential blocking or timing issues during the initial state saving after registration.
*   **Resolution 3:** Added a small `time.sleep(1)` delay in the Locust user's `on_start` method after the registration call to allow the initial state to be potentially saved before other operations.
*   **Result 3:** Re-running the short Scenario 1 test after adding the delay still resulted in 100% failures with the same registration errors. The delay did not resolve the issue.
*   **Finding 4:** Added wait-and-retry logic in `load_tests/scenario_1/locustfile.py` after registration to wait for agent state availability. This did not resolve the issue, suggesting the problem is not simply a timing issue on the client side.
*   **Finding 5:** Added detailed logging in `opscore/api.py`, `opscore/lifecycle.py`, and `opscore/storage.py` to trace registration and state saving.
*   **Finding 6:** Simplified the `/v1/opscore/internal/agent/notify` endpoint in `opscore/api.py` to a minimal implementation returning only a success response. The issue persists even with the minimal endpoint, indicating the problem is likely at a lower level than the application logic.
*   **Finding 7:** Attempted to access Ops-Core container logs directly using `docker logs` and by reading log files inside the container using `docker exec cat`. Logs remain empty, and `docker logs` resulted in an undefined exit code, preventing diagnosis of the early failure.

**Current Status:**

*   The original 500 Internal Server Errors related to workflow initiation (`NameError`) are resolved.
*   The load tests for both Scenario 1 and Scenario 2 are currently blocked by agent registration failures (`Failed to register agent: 0` and `ConnectionResetError`).
*   The root cause of the agent registration failure is still unknown. The issue appears to be occurring at a low level, likely within the FastAPI/Uvicorn server or the Docker networking layer, specifically when handling the load from Locust, before application logging can capture any details. Logs from the Ops-Core container are currently inaccessible.

**Next Steps:**

Further debugging requires resolving the issue with accessing logs from the Ops-Core container or using alternative methods to capture the container's standard output/error streams. Once logs are accessible, analyze them to pinpoint the exact cause of the "Failed to register agent: 0" error and `ConnectionResetError` during registration.

**Files Modified:**

*   `load_tests/scenario_1/locustfile.py` (Removed auth header for registration, added delay, added wait-and-retry)
*   `opscore/api.py` (Added None check in `get_agent_state` debug log, added detailed logging, simplified agent_notification endpoint)
*   `opscore/lifecycle.py` (Added detailed logging)
*   `opscore/storage.py` (Added detailed logging)
*   `TASK.md` (Updated status)
*   `memory-bank/activeContext.md` (Updated)
*   `memory-bank/progress.md` (Updated)