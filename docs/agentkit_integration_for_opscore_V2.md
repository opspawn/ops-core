# AgentKit Integration Guide for Ops-Core Developers

## 1. Introduction

### Purpose
This document provides Ops-Core developers with the necessary technical details to integrate the Ops-Core system with the AgentKit Python module. It outlines AgentKit's relevant APIs, expected data formats, communication protocols, and interaction patterns required for Ops-Core to effectively manage agent lifecycles and dispatch tasks to agents built with AgentKit.

### Scope
This guide focuses on the AgentKit side of the integration, detailing how Ops-Core should interact with AgentKit's APIs and what Ops-Core needs to provide for agents to report their status back.

### AgentKit Overview
AgentKit is a Python module designed for the rapid development and prototyping of AI agents. Its core responsibilities include:
*   **Agent Registration:** Providing an API endpoint (`POST /v1/agents/register`) for agents to register themselves and their metadata (capabilities, version, contact endpoint).
*   **Message Routing:** Offering a central API endpoint (`POST /v1/agents/{agentId}/run`) to receive messages intended for specific agents. AgentKit routes these messages to the agent's registered HTTP `contactEndpoint`.
*   **Tool Execution:** Handling `tool_invocation` message types internally by calling registered tools.
*   **SDK:** Providing a Python client library (`agentkit.sdk`) for developers to build agents that interact with the AgentKit API and, as of recent updates, directly with Ops-Core for state reporting.

### References
*   **AgentKit README:** [../README.md](../README.md)
*   **AgentKit API Docs:** Access `/docs` (Swagger) or `/redoc` on a running AgentKit instance (e.g., `http://localhost:8000/docs`).
*   **AgentKit Planning:** [../PLANNING.md](../PLANNING.md) (for architectural context).
*   **AgentKit Configuration:** [configuration.md](configuration.md)

## 2. Integration Points & Responsibilities

### Agent Registration Data
-   **Ops-Core Need:** To manage agents, Ops-Core must know which agents are registered with AgentKit and retrieve their essential metadata, particularly `agentId`, `capabilities`, and `contactEndpoint`.
-   **Mechanism Recommendation:** Ops-Core should periodically poll AgentKit's agent listing endpoint to discover registered agents and synchronize metadata.
    *   **AgentKit Endpoint:** `GET /v1/agents` (Note: This endpoint needs to be confirmed or implemented in AgentKit if not already present. Assuming it exists for this guide).
    *   **Expected Response Format (Example):**
        ```json
        {
          "status": "success",
          "message": "Agents retrieved successfully.",
          "data": [
            {
              "agentId": "agent-123",
              "agentName": "ExampleAgent",
              "version": "1.0",
              "capabilities": ["process_text", "use_calculator"],
              "contactEndpoint": "http://agent-service:8001/",
              "registrationTime": "2024-01-01T10:00:00Z",
              "metadata": {"description": "..."}
            },
            // ... other agents
          ]
        }
        ```
-   **Data Model:** The structure corresponds to AgentKit's internal representation, likely based on `agentkit.core.models.AgentInfo`.
-   **Alternative: Webhook Notification:** As an alternative or supplement to polling, Ops-Core can receive proactive notifications from AgentKit upon agent registration via a webhook. See the next section.

### Receiving Agent Registration Webhooks (Optional)
-   **Purpose:** Allows Ops-Core to be notified immediately when a new agent registers with AgentKit, avoiding the need for constant polling.
-   **Mechanism:** If configured in the AgentKit service environment (`OPSCORE_WEBHOOK_URL`, `OPSCORE_WEBHOOK_SECRET`), AgentKit will send an asynchronous POST request to the specified Ops-Core URL after an agent successfully registers via `POST /v1/agents/register`.
-   **Ops-Core Responsibility:** Ops-Core must implement an HTTP endpoint to receive these POST requests. This endpoint must:
    1.  Verify the `Content-Type: application/json` header.
    2.  Verify the HMAC-SHA256 signature using the shared `OPSCORE_WEBHOOK_SECRET`.
    3.  Process the JSON payload containing the registration details.
    4.  Return a `200 OK` or `202 Accepted` response promptly.
-   **Webhook Request Details:**
    *   **Method:** `POST`
    *   **Headers:**
        *   `Content-Type: application/json`
        *   `X-AgentKit-Timestamp`: ISO 8601 UTC timestamp string (e.g., `"2024-04-20T18:15:00.123456+00:00"`)
        *   `X-AgentKit-Signature`: Hex-encoded HMAC-SHA256 signature (see Verification below).
    *   **Body (JSON Payload):**
        ```json
        {
          "event_type": "REGISTER",
          "agent_details": {
            "agentId": "string",
            "agentName": "string",
            "version": "string",
            "capabilities": ["string"],
            "contactEndpoint": "string (url)",
            "registrationTime": "string (isoformat datetime)",
            "metadata": { ... } // Optional agent-provided metadata
          }
        }
        ```
-   **HMAC Signature Verification:** Ops-Core must verify the `X-AgentKit-Signature` to ensure the webhook is authentic.
    1.  Read the `X-AgentKit-Timestamp` header value.
    2.  Read the raw request body bytes.
    3.  Concatenate the timestamp string, a literal dot (`.`), and the raw body bytes. Example (Python bytes): `f"{timestamp_header}.".encode('utf-8') + raw_body_bytes`
    4.  Compute the HMAC-SHA256 hash of the concatenated bytes using the shared `OPSCORE_WEBHOOK_SECRET` as the key.
    5.  Convert the computed hash to a hexadecimal string.
    6.  Compare the computed hex signature with the value from the `X-AgentKit-Signature` header using a timing-safe comparison function (e.g., `hmac.compare_digest` in Python). If they match, the webhook is valid.
    7.  Optionally, check if the timestamp is within an acceptable tolerance window to prevent replay attacks.

### Dispatching Tasks/Messages to Agents
-   **Mechanism:** Ops-Core **must** dispatch tasks or commands to specific agents by sending a POST request to AgentKit's central messaging endpoint: `POST /v1/agents/{agentId}/run`.
-   **AgentKit's Role:** AgentKit acts as a message router. Upon receiving a request at `/run`:
    1.  It identifies the target agent using the `{agentId}` from the URL.
    2.  It checks the `messageType`.
    3.  **If `messageType` is `tool_invocation`:** AgentKit attempts synchronous tool execution. The response to Ops-Core will contain the tool's result or an error.
    4.  **If `messageType` is anything else (e.g., `"workflow_task"`):**
        *   AgentKit immediately returns a `202 Accepted` response to Ops-Core.
        *   AgentKit schedules a background task to forward the original JSON request body as a POST request to the agent's registered `contactEndpoint`.
-   **Required Request Payload for AgentKit `/run`:** Ops-Core must structure its request body as follows (note the optional Ops-Core specific fields recognized by AgentKit):
    ```json
    {
      "senderId": "opscore_system_id", // Use a consistent, designated ID for Ops-Core
      "messageType": "workflow_task", // Or another type agreed upon for Ops-Core tasks
      "payload": {
        // --- Ops-Core specific task details ---
        "task_name": "...",
        "task_parameters": { ... },
        // --- etc. ---
      },
      // --- Optional Ops-Core Context Fields ---
      // These are included in the message forwarded to the agent
      "task_name": "string (optional)",
      "opscore_session_id": "string (optional)",
      "opscore_task_id": "string (optional)"
    }
    ```
-   **Response Handling (Task B9 Update):**
    *   For **tool invocations**, Ops-Core receives the synchronous result (e.g., `200 OK` with tool output, or `404 Not Found` if tool unknown).
    *   For **other message types** (like workflow tasks), Ops-Core will receive a `202 Accepted` response immediately. This response confirms AgentKit has *accepted* the task for asynchronous dispatch to the agent. It **does not** indicate successful delivery to or processing by the agent.
    *   The `202 Accepted` response body looks like:
        ```json
        {
          "status": "success",
          "message": "Task accepted and scheduled for asynchronous dispatch.",
          "data": {
            "dispatch_status": "scheduled"
          }
        }
        ```
    *   Ops-Core **must** rely on the direct Agent State Updates (see next section) to track the actual processing status of the task by the agent.

### Receiving Agent State Updates
-   **Mechanism:** Ops-Core **must** implement and expose a dedicated API endpoint to receive direct state updates from AgentKit agents. The AgentKit SDK is configured to send these updates to: `POST /v1/opscore/agent/{agentId}/state`.
-   **AgentKit's Role:** AgentKit is **not** involved in proxying these state updates. Agents use the AgentKit SDK (`report_state_to_opscore` method), which reads the `OPSCORE_API_URL` environment variable and makes a direct HTTP POST request to Ops-Core.
-   **Expected Request Payload at Ops-Core `/state` Endpoint:** Ops-Core must expect and validate the following JSON structure:
    ```json
    {
      "agentId": "string", // ID of the agent reporting state
      "timestamp": "string", // ISO 8601 format UTC timestamp (e.g., "2024-01-01T12:00:00.123456+00:00")
      "state": "string", // The state being reported (e.g., "initializing", "idle", "active", "error")
      "details": { ... } // Optional, arbitrary JSON object for additional context (e.g., error messages, task progress)
    }
    ```
-   **Authentication:** Ops-Core's `/state` endpoint **must** implement authentication. The AgentKit SDK sends an API key (read from the `OPSCORE_API_KEY` environment variable) in the `Authorization` header as a Bearer token. Ops-Core must validate this token.
    *   **Expected Header:** `Authorization: Bearer <OPSCORE_API_KEY_value>`
-   **Required Responses from Ops-Core `/state` Endpoint:**
    *   **Success:** Return `200 OK` or `202 Accepted` with an optional simple JSON body like `{"status": "success"}`.
    *   **Client Errors:**
        *   `400 Bad Request`: If the payload is malformed or fails schema validation. Include error details in the response body.
        *   `401 Unauthorized`: If the `Authorization` header is missing or the token is invalid.
        *   `404 Not Found`: If the `{agentId}` in the URL is unknown to Ops-Core (though this might also be handled as a 400).
    *   **Server Errors:**
        *   `500 Internal Server Error`: If Ops-Core fails to process the state update due to an internal issue.

## 3. Sequence Diagram (Ops-Core Perspective)

```mermaid
sequenceDiagram
    participant Ops-Core Internal
    participant Ops-Core API
    participant AgentKit API
    participant AgentKit SDK
    participant Agent

    Note over Ops-Core Internal, AgentKit API: Discover/Sync Agents
    Ops-Core Internal->>AgentKit API: GET /v1/agents (Polling)
    AgentKit API-->>Ops-Core Internal: List of Agent Metadata

    Note over Ops-Core Internal, Ops-Core API: Dispatch Task
    Ops-Core Internal->>Ops-Core API: Request Task Dispatch for Agent X
    Ops-Core API->>AgentKit API: POST /v1/agents/agent-X/run (Payload: Workflow Task)
    AgentKit API-->>Ops-Core API: Task Accepted (202 Accepted)
    Ops-Core API-->>Ops-Core Internal: Dispatch Scheduled by AgentKit

    Note over AgentKit API, Agent: AgentKit Dispatches Task (Async)
    AgentKit API->>Agent: POST /contactEndpoint (Workflow Task)
    Agent-->>AgentKit API: Agent Ack (e.g., 200 OK)

    Note over Agent, AgentKit SDK: Agent Processes & Reports State
    Agent->>Agent: Process Task...
    Agent->>AgentKit SDK: report_state_to_opscore("agent-X", "active", ...)
    AgentKit SDK->>Ops-Core API: POST /v1/opscore/agent/agent-X/state (Auth Header, Payload: state="active")
    Ops-Core API-->>AgentKit SDK: State Update OK (200 OK)
    AgentKit SDK-->>Agent: Success

    Agent->>Agent: ...Finish Task
    Agent->>AgentKit SDK: report_state_to_opscore("agent-X", "idle", ...)
    AgentKit SDK->>Ops-Core API: POST /v1/opscore/agent/agent-X/state (Auth Header, Payload: state="idle")
    Ops-Core API-->>AgentKit SDK: State Update OK (200 OK)
    AgentKit SDK-->>Agent: Success
```

## 4. Implementation Checklist for Ops-Core

-   [ ] **Agent Discovery:** Implement logic to periodically poll AgentKit's `GET /v1/agents` endpoint (confirm endpoint availability/details with AgentKit team) and synchronize agent metadata (`agentId`, `contactEndpoint`, `capabilities`).
-   [ ] **Task Dispatch:** Implement logic to construct valid JSON request bodies and send POST requests to AgentKit's `POST /v1/agents/{agentId}/run` endpoint. Use a designated `senderId` for Ops-Core. Handle the `202 Accepted` response correctly, understanding it only confirms scheduling, not execution. Rely on agent state updates for actual task status.
-   [ ] **Webhook Receiver Endpoint (Optional):** If using webhooks for agent discovery:
    -   [ ] Implement an HTTP endpoint to receive POST requests from AgentKit.
    -   [ ] Verify `Content-Type: application/json`.
    -   [ ] Implement HMAC-SHA256 signature verification using the shared secret (`OPSCORE_WEBHOOK_SECRET`). Return `401 Unauthorized` or `403 Forbidden` on failure.
    -   [ ] Validate the incoming JSON payload structure (`event_type`, `agent_details`). Return `400 Bad Request` on failure.
    -   [ ] Process the valid registration data (e.g., update Ops-Core's agent registry).
    -   [ ] Return `200 OK` or `202 Accepted` promptly.
-   [ ] **State Update Endpoint:** Implement the `POST /v1/opscore/agent/{agentId}/state` endpoint:
    -   [ ] Verify `Content-Type: application/json`.
    -   [ ] Implement Authentication: Extract Bearer token from `Authorization` header and validate it. Return `401 Unauthorized` if invalid/missing.
    -   [ ] Implement Payload Validation: Parse the JSON body and validate it against the expected schema (agentId, timestamp, state, details). Return `400 Bad Request` on failure.
    -   [ ] Implement State Processing Logic: Update Ops-Core's internal representation of the agent's state based on the validated payload.
    -   [ ] Return Success Response: Return `200 OK` or `202 Accepted` on successful processing.
    -   [ ] Return Server Error Response: Return `500 Internal Server Error` if internal processing fails.
-   [ ] **Error Handling:** Implement robust error handling for network issues or non-success responses when calling AgentKit APIs.
-   [ ] **Configuration:** Allow configuration of the AgentKit API base URL, Ops-Core's own API Key (for agents), and the shared Webhook Secret within Ops-Core.

## 5. Appendix: Schema Definitions (Placeholder)

*(This section should ideally contain formal OpenAPI/JSON Schema definitions)*

### AgentKit `/run` Endpoint Request Body Schema (Informal)
```json
{
  "type": "object",
  "properties": {
    "senderId": {"type": "string", "description": "Identifier of the message sender (e.g., 'opscore_system_id')"},
    "messageType": {"type": "string", "description": "Type of message (e.g., 'workflow_task', 'tool_invocation')"},
    "payload": {"type": "object", "description": "Message content specific to the messageType"},
    "task_name": {"type": ["string", "null"], "description": "Optional Ops-Core task name"},
    "opscore_session_id": {"type": ["string", "null"], "description": "Optional Ops-Core session ID"},
    "opscore_task_id": {"type": ["string", "null"], "description": "Optional Ops-Core task ID"}
  },
  "required": ["senderId", "messageType", "payload"]
}
```

### Ops-Core `/state` Endpoint Expected Request Body Schema (Informal)
```json
{
  "type": "object",
  "properties": {
    "agentId": {"type": "string", "description": "ID of the agent reporting state"},
    "timestamp": {"type": "string", "format": "date-time", "description": "ISO 8601 UTC timestamp"},
    "state": {"type": "string", "description": "Reported state (e.g., idle, active, error)"},
    "details": {"type": ["object", "null"], "description": "Optional dictionary for additional context"}
  },
  "required": ["agentId", "timestamp", "state"]
}

### AgentKit Registration Webhook Payload Schema (Informal)
```json
{
  "type": "object",
  "properties": {
    "event_type": {"type": "string", "enum": ["REGISTER"], "description": "Type of event"},
    "agent_details": {
      "type": "object",
      "properties": {
        "agentId": {"type": "string"},
        "agentName": {"type": "string"},
        "version": {"type": "string"},
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "contactEndpoint": {"type": "string", "format": "uri"},
        "registrationTime": {"type": "string", "format": "date-time"},
        "metadata": {"type": "object"}
      },
      "required": ["agentId", "agentName", "version", "capabilities", "contactEndpoint", "registrationTime", "metadata"]
    }
  },
  "required": ["event_type", "agent_details"]
}
```