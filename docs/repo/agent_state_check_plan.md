# Plan: Implement Agent State Check in `process_next_task`

**Objective:** Implement logic within the `process_next_task` function in `opscore/workflow.py` to check the target agent's state before dispatching a task. Only dispatch if the agent is in an 'idle' state.

**Analysis:**

1.  **Agent States:** From `models.py`, the relevant states are likely `"initializing"`, `"idle"`, `"active"`, `"error"`, `"finished"`. Only `"idle"` is suitable for dispatch.
2.  **State Retrieval:** `lifecycle.py` provides a synchronous function `get_state(agent_id)` which retrieves the latest `AgentState` from storage.
3.  **Async Context:** `workflow.py::process_next_task` is an `async` function. Calling the synchronous `get_state` directly would block the event loop.
4.  **Handling Non-Idle States:** Re-enqueue the task if the agent is not idle.
5.  **Handling Unknown Agents/States:** If `get_state` returns `None`, fail the task.

**Implementation Steps:**

1.  **Modify `opscore/workflow.py` -> `process_next_task`:**
    *   Ensure `import asyncio` is present.
    *   Inside the `if task_data:` block, before dispatching, call `lifecycle.get_state` using `asyncio.to_thread`:
        ```python
        try:
            # Use asyncio.to_thread to call the sync function from async context
            current_state = await asyncio.to_thread(lifecycle.get_state, agent_id)
        except Exception as e:
            logger.error(f"Error retrieving state for agent {agent_id}: {e}", exc_info=True)
            # Decide how to handle state retrieval failure - potentially fail the task
            handle_task_failure(task_data, f"Failed to retrieve agent state: {e}")
            return # Stop processing this task
        ```
    *   Replace the current bypass logic with conditional logic based on `current_state`:
        *   If `current_state` exists and `current_state.state == 'idle'`:
            *   Log debug message.
            *   Call `await dispatch_task(agent_id, task_data)`.
            *   Include basic error logging around the dispatch call.
        *   If `current_state` exists but state is not 'idle':
            *   Log warning message.
            *   Call `enqueue_task(task_data)` to re-queue. (Add TODO for delay/backoff).
        *   If `current_state` is `None`:
            *   Log error message.
            *   Call `handle_task_failure(task_data, f"Agent state not found for agent {agent_id}")`.

2.  **Update Tests (`tests/test_workflow.py`):**
    *   Add new test cases for `process_next_task`.
    *   Use mocking (`unittest.mock.patch` or `mocker`) for `asyncio.to_thread`, `lifecycle.get_state`, `enqueue_task`, `dispatch_task`, and `handle_task_failure`.
    *   Test scenarios:
        *   Agent 'idle' -> `dispatch_task` called.
        *   Agent 'active' -> `enqueue_task` called.
        *   Agent state `None` -> `handle_task_failure` called.
        *   `lifecycle.get_state` raises exception -> `handle_task_failure` called.

**Diagram:**

```mermaid
graph TD
    A[Start process_next_task] --> B{Task in queue?};
    B -- No --> C[Log "No tasks" & End];
    B -- Yes --> D[Dequeue Task];
    D --> E{Agent ID present?};
    E -- No --> F[Log Error & End];
    E -- Yes --> G[Call asyncio.to_thread(lifecycle.get_state)];
    G --> G_Err{Error during get_state?};
    G_Err -- Yes --> G_Fail[Log Error];
    G_Fail --> J[Call handle_task_failure];
    G_Err -- No --> H{State Found (Not None)?};
    H -- No --> I[Log Error: State Not Found];
    I --> J;
    J --> K[End];
    H -- Yes --> L{State == 'idle'?};
    L -- Yes --> M[Call dispatch_task];
    M --> M_Err{Error during dispatch?};
    M_Err -- Yes --> M_Fail[Log Error (dispatch handles failure)];
    M_Fail --> K;
    M_Err -- No --> K;
    L -- No --> N[Log Warning: Agent Not Idle];
    N --> O[Call enqueue_task (Re-enqueue)];
    O --> K;

    style F fill:#f99,stroke:#333,stroke-width:2px
    style G_Fail fill:#f99,stroke:#333,stroke-width:2px
    style I fill:#f99,stroke:#333,stroke-width:2px
    style N fill:#ff9,stroke:#333,stroke-width:2px