# Ops-Core Python SDK Development Plan (Task 3.1)

## 1. Goal
Create a Python SDK (`opscore-sdk`) to provide a simple and convenient interface for developers to interact with the Ops-Core API from their Python applications or agents.

## 2. Scope & Functionality
The SDK will provide helper functions primarily for:
*   **Updating Agent State:** Calling `POST /v1/opscore/agent/{agentId}/state`.
*   **Triggering Workflows:** Calling `POST /v1/opscore/agent/{agentId}/workflow`.
*   **Getting Agent State:** Calling `GET /v1/opscore/agent/{agent_id}/state`.

*Important Note:* Since agent registration is now handled via a webhook notification from AgentKit to Ops-Core's internal endpoint (`/v1/opscore/internal/agent/notify`), the SDK will *not* include a function to directly register agents with Ops-Core. Agents are expected to receive their `agent_id` through other means (e.g., from AgentKit after registration) and then use this SDK to interact with Ops-Core using that ID.

## 3. Proposed SDK Structure & Location
The SDK will be created within this repository in a new top-level directory: `opscore_sdk/`.

```
ops-core/
├── opscore/
├── tests/
├── memory-bank/
├── mock_agentkit/
├── opscore_sdk/           <-- New SDK Directory
│   ├── __init__.py
│   ├── client.py          # Main SDK client class(es)
│   ├── models.py          # SDK-specific data models/types
│   ├── exceptions.py      # SDK-specific exceptions
│   └── README.md          # Basic usage guide
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── PLANNING.md
├── TASK.md
└── ... (other files)
```

## 4. Technical Details
*   **HTTP Client:** Use `httpx` (already added as a dependency for integration tests) for making HTTP requests. This allows for both synchronous and asynchronous client implementations.
*   **Client Implementation:** Create both synchronous (`OpsCoreClientSync`) and asynchronous (`OpsCoreClientAsync`) client classes in `opscore_sdk/client.py`.
*   **Configuration:** The clients will be initialized with the Ops-Core `base_url` and `api_key`.
*   **Models:** Define simple data classes or TypedDicts in `opscore_sdk/models.py` for required inputs (e.g., state update payload) and potentially simplified outputs, keeping the SDK decoupled from the main `opscore.models`.
*   **Error Handling:** Define custom exceptions in `opscore_sdk/exceptions.py` (e.g., `OpsCoreApiError`, `AuthenticationError`, `NotFoundError`) to wrap HTTP errors and potential API-specific errors returned by Ops-Core.
*   **Dependencies:** Ensure `httpx` is listed appropriately in `requirements.txt` for general use, not just testing.

## 5. Development Steps
    a. Create the `opscore_sdk/` directory and initial files (`__init__.py`, `client.py`, `models.py`, `exceptions.py`, `README.md`).
    b. Define basic SDK exceptions in `exceptions.py`.
    c. Define necessary input/output data structures in `models.py`.
    d. Implement the `OpsCoreClientSync` class with methods for `update_state`, `trigger_workflow`, and `get_state`. Include error handling and API key usage.
    e. Implement the `OpsCoreClientAsync` class mirroring the sync client's functionality using `async/await` and `httpx`'s async capabilities.
    f. Add basic usage instructions to `opscore_sdk/README.md`.
    g. Add `httpx` to the main dependencies in `requirements.txt` if necessary.
    h. Create a new test directory `tests/test_opscore_sdk/`.
    i. Write unit tests for both sync and async clients, mocking HTTP requests/responses using `httpx`'s mocking features or a library like `pytest-httpx`.