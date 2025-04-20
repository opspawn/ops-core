# AgentKit Requirements for Ops-Core Integration (Comprehensive)

This document tracks features and API specifications required from the AgentKit service and its associated SDK for seamless integration with Ops-Core.

## 1. Agent Discovery/Registration Webhooks (Required for Task 3.4 - Webhook Approach)

*   **Requirement:** AgentKit needs the capability to send webhook notifications (HTTP POST) to a configurable Ops-Core endpoint upon agent registration and deregistration events. This allows Ops-Core to maintain an up-to-date registry of available agents without constant polling.
*   **Trigger:** Agent registration (e.g., via `POST /v1/agents`) or deregistration (if applicable).
*   **Target Endpoint (Ops-Core):** Configurable URL provided to AgentKit (e.g., via environment variable `OPSCORE_WEBHOOK_URL`). Ops-Core exposes `POST /v1/opscore/internal/agent/notify`.
*   **Payload:** The webhook payload MUST contain:
    *   `event_type`: String (e.g., "REGISTER", "DEREGISTER").
    *   `agent_details`: Object containing the full agent information matching Ops-Core's `AgentRegistrationDetails` model (defined in `opscore/models.py`), including `agentId`, `agentName`, `version`, `capabilities`, `contactEndpoint`, and `metadata`.
*   **Authentication:** The mechanism for securing this webhook (e.g., shared secret, signature) is TBD but necessary.
*   **Status:** Pending implementation/confirmation in the real AgentKit service. Mock implementation simulates this.

## 2. Task Dispatch Endpoint

*   **Requirement:** AgentKit MUST expose an endpoint for Ops-Core to dispatch tasks to specific, registered agents.
*   **Endpoint:** `POST /v1/agents/{agent_id}/run`
*   **Request Payload:** Ops-Core will send a payload containing the task details (e.g., task name/ID, parameters). The exact schema is TBD but should allow passing arbitrary parameters relevant to the agent's capability.
    ```json
    {
      "task_name": "example_task",
      "parameters": {
        "param1": "value1",
        "param2": 123
      }
      // Potentially include Ops-Core session/task IDs for correlation
      "opscore_session_id": "...",
      "opscore_task_id": "..."
    }
    ```
*   **Response:** AgentKit should acknowledge receipt (e.g., `202 Accepted`) and handle the asynchronous execution of the task by the agent. AgentKit does *not* need to wait for task completion before responding to Ops-Core.
*   **Status:** Assumed core functionality of AgentKit, but confirmation of endpoint and payload schema needed. Mock implementation simulates a basic version.

## 3. Agent State Update Callback (via AgentKit SDK)

*   **Requirement:** Agents managed by AgentKit (and using its SDK) MUST report their status back to Ops-Core after attempting a task dispatched by Ops-Core. This is critical for Ops-Core's workflow tracking.
*   **Trigger:** Agent completes or fails a task initiated via the `POST /v1/agents/{agent_id}/run` endpoint.
*   **Mechanism:** The AgentKit SDK used by the agent should facilitate or enforce sending a state update to Ops-Core.
*   **Target Endpoint (Ops-Core):** `POST /v1/opscore/agent/{agent_id}/state`
*   **Payload:** The agent (via SDK) MUST send a payload matching Ops-Core's `AgentStateUpdatePayload` model (defined in `opscore/models.py`), including:
    *   `agentId`: The ID of the agent.
    *   `state`: The new state ("idle", "finished", "error", etc.).
    *   `details`: Optional dictionary containing task results or error information.
    *   `timestamp`: ISO 8601 timestamp of the state change.
*   **Authentication:** The SDK MUST handle authenticating this call to Ops-Core using the configured API Key (`OPSCORE_API_KEY`, passed as a Bearer token).
*   **Configuration:** The SDK needs access to the Ops-Core API base URL (`OPSCORE_API_URL`) and the API Key (`OPSCORE_API_KEY`), likely via environment variables or configuration passed during agent initialization.
*   **Status:** This is a CRITICAL requirement for Ops-Core integration. Confirmation needed that the AgentKit SDK will handle this callback reliably. Mock implementation simulates this callback after a delay upon receiving a task via `/run`.

## 4. Testing Notes for AgentKit Developers

*   **Mocking Ops-Core:** To test AgentKit's webhook and task dispatch functionalities without a running Ops-Core instance, you can stand up a simple mock HTTP server (e.g., using Python's `http.server` or Flask/FastAPI) that listens on the configured Ops-Core endpoints:
    *   **Webhook Receiver (`POST /v1/opscore/internal/agent/notify`):** The mock should simply accept the POST request, optionally validate the payload structure against the spec in section 1, and return a `200 OK` response.
    *   **State Update (`POST /v1/opscore/agent/{agent_id}/state`):** The mock should accept the POST request, validate the `Authorization: Bearer <key>` header, validate the payload against the `AgentStateUpdatePayload` structure (section 3), and return a `202 Accepted` response.
    *   **Get State (`GET /v1/opscore/agent/{agent_id}/state`):** (Optional) If testing SDK features that might read state, the mock can return a valid `AgentState` JSON object.
*   **Testing Webhooks:** Configure AgentKit to point to your mock Ops-Core webhook receiver URL. Trigger agent registration in AgentKit and verify the mock server receives the correct `REGISTER` event payload.
*   **Testing State Callbacks:** Configure the AgentKit SDK (within a test agent) to point to your mock Ops-Core API URL and provide a dummy API key. Trigger a task on the agent via AgentKit's `/run` endpoint. Verify that the agent (using the SDK) makes the correct `POST` call to the mock `/state` endpoint with the expected payload and Bearer token after the task simulation completes.
*   **Docker Compose:** The Ops-Core repository contains a `docker-compose.yml` with a `mock-agentkit` service that can serve as a reference for simulating AgentKit's behavior from Ops-Core's perspective.