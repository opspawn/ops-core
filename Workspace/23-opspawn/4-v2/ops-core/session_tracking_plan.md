# Plan for Task 2.4: Implement Session Tracking

**Objective:** Implement session and workflow tracking functions (`start_session`, `update_session`, `get_session`) in `opscore/lifecycle.py`.

**Date:** 2025-04-17

**Plan Details:**

1.  **Define Data Models (`opscore/models.py`):**
    *   Add the `Session` Pydantic model with fields: `session_id` (UUID), `agent_id` (str), `workflow_id` (str), `status` (str, default "active"), `start_time` (datetime), `last_updated_time` (datetime), `metadata` (Optional Dict).
    *   Add the `SessionUpdate` Pydantic model with optional fields: `status` (str), `metadata` (Dict).

2.  **Enhance Storage Layer (`opscore/storage.py`):**
    *   Add a new dictionary `_sessions: Dict[str, Session]` to store active sessions, keyed by `session_id`.
    *   Add a corresponding `threading.Lock` for `_sessions` to ensure thread safety.
    *   Implement the following storage functions:
        *   `create_session(session: Session) -> None`: Adds a new session to `_sessions`. Raises an error if the ID already exists.
        *   `read_session(session_id: str) -> Optional[Session]`: Retrieves a session by ID. Returns `None` if not found.
        *   `update_session_data(session_id: str, update_data: Dict[str, Any]) -> Session`: Updates specific fields of an existing session. Updates `last_updated_time`. Raises an error if the session doesn't exist. Returns the updated session.
        *   `delete_session(session_id: str) -> bool`: Removes a session by ID. Returns `True` if successful, `False` if not found. (Lower priority for initial implementation).

3.  **Implement Lifecycle Functions (`opscore/lifecycle.py`):**
    *   **`start_session(agent_id: str, workflow_id: str) -> Session`:**
        *   Verify the `agent_id` exists using `storage.read_agent`. Raise an appropriate error (e.g., `ValueError` or a custom exception) if not found.
        *   Create a new `Session` instance.
        *   Store the session using `storage.create_session`.
        *   Log the creation event.
        *   Return the created `Session` object.
    *   **`update_session(session_id: str, update_data: SessionUpdate) -> Session`:**
        *   Retrieve the existing session using `storage.read_session`. Raise an error if not found.
        *   Convert `update_data` (Pydantic model) into a dictionary, excluding any fields that were not explicitly set (`exclude_unset=True`).
        *   Add `last_updated_time: datetime.utcnow()` to the update dictionary.
        *   Call `storage.update_session_data` with the `session_id` and the update dictionary.
        *   Log the update event.
        *   Return the updated `Session` object returned by the storage layer.
    *   **`get_session(session_id: str) -> Optional[Session]`:**
        *   Retrieve the session using `storage.read_session`.
        *   Log the retrieval attempt (success or failure).
        *   Return the `Session` object or `None`.

4.  **Add Imports:** Ensure necessary imports (`datetime`, `uuid`, `Optional`, `Dict`, `Any`, `Field`, `BaseModel` from `pydantic`, relevant storage functions, logging) are correctly added in `opscore/models.py`, `opscore/storage.py`, and `opscore/lifecycle.py`.

**Visual Plan (Mermaid):**

```mermaid
graph TD
    subgraph File: opscore/models.py
        M1[Define Session Model]
        M2[Define SessionUpdate Model]
    end

    subgraph File: opscore/storage.py
        S1[Add _sessions Dict & Lock]
        S2[Implement create_session]
        S3[Implement read_session]
        S4[Implement update_session_data]
        S5[Implement delete_session (Optional)]
    end

    subgraph File: opscore/lifecycle.py
        L1[Implement start_session]
        L2[Implement update_session]
        L3[Implement get_session]
    end

    M1 --> L1
    M2 --> L2
    S1 --> S2 & S3 & S4 & S5

    L1 -- Calls --> S2
    L1 -- Calls --> storage.read_agent
    L2 -- Calls --> S3 & S4
    L3 -- Calls --> S3

    L1 -- Logs --> Logging
    L2 -- Logs --> Logging
    L3 -- Logs --> Logging