# Detailed Plan: Implement Redis Storage for Integration Tests (Task 4.2)

## 1. Objective

Resolve the integration test failure (`TimeoutError` with 404s) in `tests/integration/test_real_agentkit_workflow.py` (Task 4.2) by replacing the `InMemoryStorage` with a `RedisStorage` backend specifically for the real AgentKit integration test environment. This addresses the identified storage visibility/timing issue across concurrent contexts.

## 2. Implementation Steps

### Step 2.1: Update Docker Compose Configuration (`docker-compose.real-agentkit.yml`)

*   **Add Redis Service:**
    *   Define a new service named `redis`.
    *   Use the official `redis:alpine` image (or a similar recent version).
    *   Expose the default Redis port `6379`.
    *   Ensure it's on the same network as `opscore_service_real`.
*   **Modify Ops-Core Service (`opscore_service_real`):**
    *   Add `redis` to the `depends_on` list.
    *   Add the following environment variables:
        *   `OPSCORE_STORAGE_TYPE=redis` (To signal Ops-Core to use Redis)
        *   `REDIS_HOST=redis` (Hostname matching the service name)
        *   `REDIS_PORT=6379` (Default Redis port)

### Step 2.2: Add Python Dependencies (`requirements.txt`)

*   Add the `redis` package to `requirements.txt`. Ensure the version supports async operations (e.g., `redis>=4.2.0rc1` or later, which bundles `aioredis`).

### Step 2.3: Implement Redis Storage Backend (`opscore/storage.py`)

*   **Import necessary libraries:** `redis.asyncio as redis`, `json`, relevant models from `opscore.models`, custom exceptions from `opscore.exceptions`.
*   **Create `RedisStorage` Class:**
    *   Implement the same interface as `InMemoryStorage` (methods like `save_agent_state`, `read_latest_agent_state`, `save_workflow_definition`, etc.).
    *   **Initialization (`__init__`)**:
        *   Accept `host` and `port` arguments.
        *   Create an async Redis connection pool (`redis.ConnectionPool`).
        *   Create a Redis client instance using the pool (`redis.Redis(connection_pool=...)`).
    *   **Serialization:** Use `json.dumps` to serialize complex Python objects (like `AgentState`, `WorkflowDefinition`) before storing them in Redis. Use `json.loads` after retrieving them. Handle potential `TypeError` during serialization and `JSONDecodeError` during deserialization.
    *   **Redis Commands:**
        *   `save_agent_state`: Use `HSET` to store agent states, perhaps keyed by `agent_id` with a field for the timestamp or a specific key structure like `agent:{agent_id}:state:{timestamp}`. Alternatively, use `SET` with a key like `agent:{agent_id}:latest_state` storing the JSON serialized state. Consider using Redis transactions (`pipeline`) for atomicity if multiple operations are needed.
        *   `read_latest_agent_state`: Use `HGET` or `GET` depending on the chosen storage structure. Handle cases where the key doesn't exist (return `None`).
        *   `save_workflow_definition`: Use `SET` with a key like `workflow_def:{definition_id}` storing the JSON serialized definition.
        *   `read_workflow_definition`: Use `GET` with the corresponding key. Handle non-existence.
        *   *(Implement other required storage methods similarly)*
    *   **Error Handling:** Wrap Redis operations in `try...except` blocks to catch potential `redis.RedisError` exceptions and raise appropriate custom `OpsCoreStorageError` exceptions.

### Step 2.4: Implement Conditional Storage Selection

*   **Location:** Modify the part of the code where the storage instance is created. This might be in `opscore/api.py` during app startup or potentially within `opscore/storage.py` using a factory function.
*   **Logic:**
    *   Read environment variables: `OPSCORE_STORAGE_TYPE`, `REDIS_HOST`, `REDIS_PORT`. Use sensible defaults if needed, although the integration test environment will provide them.
    *   If `OPSCORE_STORAGE_TYPE == 'redis'`:
        *   Instantiate `RedisStorage(host=REDIS_HOST, port=REDIS_PORT)`.
    *   Else:
        *   Instantiate `InMemoryStorage()`.
    *   Pass the chosen storage instance to the components that need it (e.g., `lifecycle`, `workflow`). This might involve dependency injection if using FastAPI's features.

### Step 2.5: Update Test Environment & Fixtures

*   **Redis Connection Fixture (`tests/conftest.py` or similar):**
    *   Create an `async` fixture (e.g., `redis_client`) that connects to the test Redis instance (using host/port from environment variables or defaults matching compose).
    *   Yield the connected client.
    *   Ensure proper cleanup (closing the connection/pool).
*   **Test Data Cleanup Fixture (`tests/conftest.py`):**
    *   Create an `async` fixture (e.g., `clear_redis_before_test`) with `scope='function'` and `autouse=True` (or apply it specifically to integration tests).
    *   This fixture should depend on the `redis_client` fixture.
    *   Before the test yields (`yield`), execute the `await redis_client.flushdb()` command to clear the database.
    *   Modify or remove the old `clear_storage_before_each_test` fixture if it conflicts or is no longer needed for integration tests running with Redis.

## 3. Verification

*   Run the integration test suite, specifically `tests/integration/test_real_agentkit_workflow.py`, using the `docker-compose.real-agentkit.yml` environment.
*   Confirm that the test now passes, successfully polling and finding the "UNKNOWN" state after agent registration, and completing the full workflow state transitions.
*   Verify that unit tests still pass using the `InMemoryStorage`.

## 4. Diagram

```mermaid
graph TD
    subgraph Test Environment (docker-compose.real-agentkit.yml)
        IntegrationTest[Integration Test (pytest on host)] -- HTTP Requests --> OpsCore[Ops-Core Service (Container)];
        IntegrationTest -- HTTP Requests --> SimAgent[Simulated Agent (Container)];
        OpsCore -- Uses Storage --> Redis[Redis Service (Container)];
        OpsCore -- API Calls --> AgentKit[AgentKit Service (Container)];
        SimAgent -- Registers via --> AgentKit;
        AgentKit -- Webhook --> OpsCore;
    end

    style Redis fill:#fcc,stroke:#333,stroke-width:2px