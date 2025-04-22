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

**Current Status:**

*   The original 500 Internal Server Errors related to workflow initiation (`NameError`) are resolved.
*   The load tests for both Scenario 1 and Scenario 2 are currently blocked by agent registration failures (`Failed to register agent: 0` and `ConnectionResetError`).
*   The root cause of the agent registration failure is still unknown. It appears the `/v1/opscore/internal/agent/notify` endpoint is not successfully completing the agent registration process, or the subsequent state saving is failing in a way that leads to connection resets for the Locust client.

**Next Steps:**

The next debugging session should focus specifically on the agent registration process (`/v1/opscore/internal/agent/notify` endpoint) and its interaction with the storage layer (`opscore/lifecycle.py` and `opscore/storage.py`) to understand why the registration is failing with status 0 and causing connection resets for the Locust clients. This may involve:

*   Adding more detailed logging within the `agent_notification` endpoint and the `lifecycle.register_agent` function to pinpoint the exact point of failure.
*   Examining the Redis logs (if accessible) to see if registration data is being received and processed.
*   Further scrutinizing the `RedisStorage.save_agent_registration` and `RedisStorage.save_agent_state` methods for potential issues.

**Files Modified:**

*   `load_tests/scenario_1/locustfile.py` (Removed auth header for registration, added delay)
*   `opscore/api.py` (Added None check in `get_agent_state` debug log)
*   `TASK.md` (Will be updated)
*   `memory-bank/activeContext.md` (Will be updated)
*   `memory-bank/progress.md` (Will be updated)