# Active Context: Ops-Core Python Module (Updated - 2025-04-17 @ 21:07)

## 1. Current Work Focus
- **Completed:** Phase 1 (Initialization & Research), Phase 2 foundational components (Lifecycle, Workflow, Storage, Logging, Models, API state endpoint), Task 2.4 (Session Tracking), Task 2.7 (Error Handling Placeholders), AgentKit Client Placeholder, Dispatcher Connection, Task 4.1 (Initial Unit Tests), API Testing (Task 4.1/4.2), Agent State Check (Task 2.6 refinement), Task 2.14 (Custom Exceptions).
- **Focus:** Implementing core features, establishing initial test coverage, and improving error handling.

## 2. Recent Changes & Decisions (This Session)
- **Workflow (Agent State Check):** Implemented agent state checking in `workflow.process_next_task` using `asyncio.to_thread` to call the synchronous `lifecycle.get_state`. Tasks are now only dispatched if the agent state is 'idle'; otherwise, they are re-enqueued (basic re-queue for now) or failed if the state cannot be determined. Added corresponding unit tests in `tests/test_workflow.py`.
- **Custom Exceptions (Task 2.14 - Completed):**
    - Created `opscore/exceptions.py` with exception hierarchy (OpsCoreError, AgentNotFoundError, SessionNotFoundError, WorkflowDefinitionNotFoundError, InvalidStateError, StorageError, RegistrationError, WorkflowDefinitionError, TaskDispatchError, ConfigurationError).
    - Refactored `opscore/lifecycle.py`, `opscore/workflow.py`, `opscore/storage.py`, and `opscore/api.py` to import and raise appropriate custom exceptions instead of generic ones (e.g., ValueError, IOError, KeyError).
    - Updated tests in `tests/test_lifecycle.py`, `tests/test_workflow.py`, `tests/test_storage.py`, and `tests/test_api.py` to expect these custom exceptions and verify correct HTTP status code mappings.

## 3. Next Steps (Next Session)
- **Integrate Ops-Core API with Python SDK (Task 3.1):** Develop helper functions to simplify API calls for registration, state update, and workflow trigger. (Next Action)
- **Refine Workflow Definition:** Define and validate the schema for `WorkflowDefinition.tasks` more strictly in `models.py`.
- **Refine Re-queue Logic:** Implement proper delay/backoff for re-queuing tasks when agents are busy (currently immediate re-queue).

## 4. Active Decisions & Considerations
- **Test Coverage:** `lifecycle.py` coverage is 100%. `api.py` coverage is 89%. Overall coverage is significantly improved but can be further enhanced, especially for `agentkit_client.py`, `logging_config.py`, `workflow.py`, and `storage.py`. Need to run coverage report again after recent changes.
- **AgentKit Endpoint Dependency:** `GET /v1/agents` endpoint confirmation still pending for full AgentKit integration.
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