# Active Context: Ops-Core Python Module (Updated - 2025-04-19 @ 07:41)

## 1. Current Work Focus
- **Completed:** Phase 1 (Initialization & Research), Phase 2 foundational components (Lifecycle, Workflow, Storage, Logging, Models, API state endpoint), Task 2.4 (Session Tracking), Task 2.7 (Error Handling Placeholders), AgentKit Client Placeholder, Dispatcher Connection, Task 4.1 (Initial Unit Tests), API Testing (Task 4.1/4.2), Agent State Check (Task 2.6 refinement), Task 2.14 (Custom Exceptions).
- **Focus:** Implementing core features, establishing initial test coverage, and improving error handling.

## 2. Recent Changes & Decisions (This Session)
- **Task 3.1 (Completed): Integrate Ops-Core API with Python SDK:**
   - Created new `opscore_sdk/` directory.
   - Implemented synchronous (`OpsCoreClientSync`) and asynchronous (`OpsCoreClientAsync`) clients in `opscore_sdk/client.py` using `httpx`.
   - Defined SDK-specific models (`StateUpdatePayload`, `WorkflowTriggerPayload`, etc.) in `opscore_sdk/models.py` using `TypedDict`.
   - Defined SDK-specific exceptions (`OpsCoreSDKError`, `OpsCoreApiError`, etc.) in `opscore_sdk/exceptions.py`.
   - Added basic usage documentation in `opscore_sdk/README.md`.
   - Added `pytest-httpx` dependency to `requirements.txt`.
   - Created unit tests for both clients in `tests/test_opscore_sdk/test_client.py`, mocking API calls with `pytest-httpx`.
   - Resolved issues with `pytest-asyncio` fixture handling for async client tests.
   - Created `sdk_development_plan.md`.
- **Task 3.4 (Completed - Previous Session): AgentKit Integration - Webhook Approach:**
   - (Details from previous session remain relevant)

## 3. Next Steps (Next Session)
- **Create CLI Application (Task 3.2):** Develop a simple CLI application to interact with Ops‑Core endpoints using the new SDK. (Next Action)
- **Refine Workflow Definition:** Define and validate the schema for `WorkflowDefinition.tasks` more strictly in `models.py`.
- **Refine Re-queue Logic:** Implement proper delay/backoff for re-queuing tasks when agents are busy (currently immediate re-queue).

## 4. Active Decisions & Considerations
- **Test Coverage:** `lifecycle.py` coverage is 100%. `api.py` coverage is 89%. Overall coverage is significantly improved but can be further enhanced, especially for `agentkit_client.py`, `logging_config.py`, `workflow.py`, and `storage.py`. Need to run coverage report again after recent changes.
- **AgentKit Endpoint Dependency:** Switched to webhook approach. Requirement for AgentKit to send webhooks documented in `AGENTKIT_REQUIREMENTS.md`. Mock AgentKit simulates this.
- **Integration Tests:** AgentKit integration tests are now passing after debugging.
- **Persistent Queue:** The task queue (`_task_queue` in `workflow.py`) remains in-memory.
- **Error Handling:** Custom exception refactoring is complete. All core modules and tests updated to use custom exceptions.
- **Agent State Check:** Implemented in `process_next_task`. Uses `asyncio.to_thread` for sync `get_state` call. Re-queues if not idle, fails if state unknown.

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