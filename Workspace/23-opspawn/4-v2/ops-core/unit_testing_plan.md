# Plan: Unit Testing for Ops-Core Subsystems (Task 4.1)

**Objective:** Implement comprehensive unit tests using `pytest` for the core functionalities developed in `opscore/storage.py`, `opscore/lifecycle.py`, and `opscore/workflow.py` to ensure correctness, handle edge cases, and validate error handling.

**Date:** 2025-04-17

**1. Setup & Configuration:**

*   **Dependencies:**
    *   Verify `pytest` is listed in `requirements.txt`.
    *   Add `pytest-asyncio` to `requirements.txt` for testing `async` functions (like those in `workflow.py` calling the agentkit client).
    *   *Action:* Check `requirements.txt` and add `pytest-asyncio` if missing.
*   **Test Directory Structure:**
    *   Ensure the `tests/` directory exists at the project root.
    *   Create test files mirroring the `opscore` structure:
        *   `tests/test_storage.py`
        *   `tests/test_lifecycle.py`
        *   `tests/test_workflow.py`
    *   Create `tests/__init__.py` (if not already present).
    *   Create `tests/conftest.py` for shared fixtures.

**2. Shared Fixtures (`tests/conftest.py`):**

*   **`clear_storage` fixture:**
    *   Scope: `function` (runs before each test function).
    *   Action: Calls `opscore.storage.clear_all_data()` to ensure a clean state for each test. Use `autouse=True` for automatic application.
*   **Sample Data Fixtures:**
    *   `valid_agent_reg_details()`: Returns a valid `AgentRegistrationDetails` model instance.
    *   `valid_agent_info()`: Returns a valid `AgentInfo` model instance (can depend on `valid_agent_reg_details`).
    *   `valid_agent_state()`: Returns a valid `AgentState` model instance.
    *   `valid_workflow_def_dict()`: Returns a dictionary representing a valid workflow definition.
    *   `valid_workflow_def_model()`: Returns a valid `WorkflowDefinition` model instance (can depend on `valid_workflow_def_dict`).
    *   `valid_session_model()`: Returns a valid `WorkflowSession` model instance.
    *   `valid_task_data_dict()`: Returns a dictionary representing valid data for `models.Task`.
*   **(Optional/Future) Mock Fixtures:**
    *   Consider fixtures for mocking external dependencies like the `agentkit_client` if needed for more isolated workflow tests later.

**3. Test Implementation Strategy (General):**

*   **Naming Convention:** Test functions should start with `test_`. Test classes (if used) should start with `Test`.
*   **Structure:** Group related tests within files (e.g., all storage tests in `test_storage.py`). Use classes to group tests for specific functions if helpful.
*   **Assertions:** Use standard `assert` statements. Check return values, state changes in storage (by reading back data), and raised exceptions (`pytest.raises`).
*   **Test Cases per Function:** Aim for coverage of:
    *   **Happy Path:** Standard successful execution.
    *   **Edge Cases:** Empty inputs, specific values, boundaries.
    *   **Error Cases:** Invalid inputs, non-existent IDs, expected exceptions.
    *   **State Verification:** Assert that storage reflects the expected changes after function calls.
*   **Async Tests:** Mark tests for `async` functions with `@pytest.mark.asyncio`.
*   **Coverage Goal:** Aim for at least 80% line coverage for the tested modules (`storage.py`, `lifecycle.py`, `workflow.py`). Use `pytest-cov` to measure.

**4. Specific Test Modules & Cases:**

*   **`tests/test_storage.py`:**
    *   Test `save/read_agent_registration` (success, read non-existent).
    *   Test `agent_exists` (true, false).
    *   Test `get_all_agent_registrations` (empty, multiple).
    *   Test `save/read_latest_agent_state` (success, read non-existent).
    *   Test `read_agent_state_history` (empty, multiple states).
    *   Test `create_session` (success, duplicate ID raises `ValueError`).
    *   Test `read_session` (found, not found).
    *   Test `update_session_data` (success, session not found raises `KeyError`, invalid data raises `ValueError`).
    *   Test `delete_session` (success returns `True`, not found returns `False`).
    *   Test `save/read_workflow_definition` (success, read non-existent).
    *   Test `clear_all_data` (verify storage dicts are empty after call).

*   **`tests/test_lifecycle.py`:**
    *   Test `register_agent` (success returns `AgentInfo`, invalid details raises `ValueError`). Verify agent saved in storage.
    *   Test `set_state` (success, agent not found raises `ValueError`). Verify state saved in storage.
    *   Test `get_state` (found returns `AgentState`, not found returns `None`).
    *   Test `start_session` (success returns `WorkflowSession`, agent not found raises `ValueError`). Verify session saved in storage.
    *   Test `update_session` (success returns updated `WorkflowSession`, session not found raises `ValueError`, empty update payload). Verify session updated in storage.
    *   Test `get_session` (found returns `WorkflowSession`, not found returns `None`).

*   **`tests/test_workflow.py`:**
    *   Test `load_workflow_template` (valid YAML, valid JSON, invalid format raises `ValueError`, invalid content raises `ValueError`).
    *   Test `create_workflow` (success, ID generation). Verify definition saved in storage.
    *   Test `get_workflow_definition` (found, not found).
    *   Test `enqueue_task` (success, invalid task data raises `ValueError`). Verify queue length increases.
    *   Test `dequeue_task` (success returns task dict, empty queue returns `None`). Verify queue length decreases.
    *   **Error Handling Placeholders:**
        *   Test `handle_task_failure`: Use `mocker` (from `pytest-mock`) to patch `retry_task` and `fallback_task`. Verify the correct one is called based on `retry_count`. Check logs.
        *   Test `retry_task`: Use `mocker` to patch `enqueue_task`. Verify it's called with updated `retryCount`. Check logs.
        *   Test `fallback_task`: Use `mocker` to patch `lifecycle.update_session` (or check logs for the debug message). Verify expected logging.
    *   **Async Functions (Requires `pytest-asyncio` and mocking):**
        *   `@pytest.mark.asyncio`
        *   Test `process_next_task`: Mock `dequeue_task`, `dispatch_task`. Test scenarios: empty queue, task dequeued & dispatched.
        *   `@pytest.mark.asyncio`
        *   Test `dispatch_task`: Mock `agentkit_client.dispatch_task_to_agentkit` (to simulate success and `ConnectionError`). Mock `handle_task_failure`. Verify client is called with correct payload. Verify `handle_task_failure` called on error.

**5. Documentation:**

*   Create a new file `unit_testing_plan.md` in the project root.
*   Copy this plan into the file. (This step)

**6. Execution:**

*   Switch back to Code mode.
*   Implement the plan step-by-step, starting with `requirements.txt` updates, then `conftest.py`, and then each `test_*.py` file.
*   Run tests frequently using the `pytest` command in the terminal.

**Visual Plan (Mermaid):**

```mermaid
graph TD
    subgraph Setup
        Req[Update requirements.txt]
        Struct[Create tests/ dir structure]
        Conf[Create tests/conftest.py]
    end

    subgraph Fixtures (conftest.py)
        F1[clear_storage fixture]
        F2[Sample data fixtures]
    end

    subgraph Test Modules
        T1[tests/test_storage.py]
        T2[tests/test_lifecycle.py]
        T3[tests/test_workflow.py]
    end

    subgraph Test Cases (General)
        C1[Happy Path]
        C2[Edge Cases]
        C3[Error Cases (Exceptions)]
        C4[State Verification]
    end

    Setup --> Fixtures
    Fixtures --> Test Modules
    Test Modules --> C1 & C2 & C3 & C4

    T1 -- Covers --> opscore/storage.py
    T2 -- Covers --> opscore/lifecycle.py
    T3 -- Covers --> opscore/workflow.py

    T3 -- Requires --> PytestAsyncio[pytest-asyncio]
    T3 -- Requires --> PytestMock[pytest-mock]

    Req --> PytestAsyncio

    Start[Start Task 4.1] --> Setup
    Test Modules --> RunTests[Run pytest]
    RunTests --> Finish[Task Complete]