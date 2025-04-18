# Active Context: Ops-Core Python Module (Updated - 2025-04-18 @ 06:09)

## 1. Current Work Focus
- **Completed:** Phase 1 (Initialization & Research), Phase 2 foundational components (Lifecycle, Workflow, Storage, Logging, Models, API state endpoint), Task 2.4 (Session Tracking), Task 2.7 (Error Handling Placeholders), AgentKit Client Placeholder, Dispatcher Connection, Task 4.1 (Initial Unit Tests), API Testing (Task 4.1/4.2), Agent State Check (Task 2.6 refinement), Task 2.14 (Custom Exceptions).
- **Focus:** Implementing core features, establishing initial test coverage, and improving error handling.

## 2. Recent Changes & Decisions (This Session)
- **Task 3.4 (Partial): Mock AgentKit Integration:**
    - Updated `docker-compose.yml` to include a mock `agentkit` service using `python:3.11-slim` image and installing FastAPI/Uvicorn.
    - Created `mock_agentkit/main.py` implementing basic `GET /v1/agents`, `POST /v1/agents`, and `POST /v1/agents/{agentId}/run` endpoints.
    - Configured Ops-Core service in `docker-compose.yml` to use the mock AgentKit via `AGENTKIT_API_URL=http://agentkit_service:80`.
    - Created `tests/test_agentkit_integration.py` with initial tests for agent registration/discovery and task dispatch via the mock AgentKit. Tests are passing.
    - Created `task_3.4_agentkit_integration_plan.md` to document the integration plan.
- **Task Prioritization:** Updated `TASK.md`, `activeContext.md`, and `progress.md` to prioritize Task 3.4 (AgentKit Integration) before Task 3.1 (SDK Development).

## 3. Next Steps (Next Session)
- **Ensure all endpoints interoperate seamlessly with AgentKit’s integration interfaces (Task 3.4):** Continue integration testing, focusing on workflow scenarios involving state updates from the (mock) agent back to Ops-Core. Implement agent registration within Ops-Core based on polling AgentKit (or alternative mechanism). (Next Action)
- **Integrate Ops-Core API with Python SDK (Task 3.1):** Develop helper functions to simplify API calls for registration, state update, and workflow trigger.
- **Refine Workflow Definition:** Define and validate the schema for `WorkflowDefinition.tasks` more strictly in `models.py`.
- **Refine Re-queue Logic:** Implement proper delay/backoff for re-queuing tasks when agents are busy (currently immediate re-queue).

## 4. Active Decisions & Considerations
- **Test Coverage:** `lifecycle.py` coverage is 100%. `api.py` coverage is 89%. Overall coverage is significantly improved but can be further enhanced, especially for `agentkit_client.py`, `logging_config.py`, `workflow.py`, and `storage.py`. Need to run coverage report again after recent changes.
- **AgentKit Endpoint Dependency:** `GET /v1/agents` endpoint confirmation still pending for full AgentKit integration. Mock implementation exists, but real integration requires confirmation. Ops-Core currently lacks agent registration logic based on AgentKit discovery.
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