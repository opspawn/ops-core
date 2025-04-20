# AgentKit Requirements for Ops-Core Integration (V2)

## 1. Introduction

This document outlines essential modifications required in the AgentKit service to ensure successful integration and testing with the Ops-Core module. These requirements stem from issues identified during integration testing using `docker-compose.real-agentkit.yml`.

## 2. Required Changes

### 2.1. Standard Health Check Endpoint

*   **Requirement:** Implement a standard health check endpoint.
*   **Path:** `/health` (at the application root)
*   **Method:** `GET`
*   **Response:**
    *   **Success (200 OK):** Return a simple JSON body indicating health, e.g., `{"status": "healthy"}` or `{"status": "ok"}`.
    *   **Failure (5xx):** Standard FastAPI error responses if the service is unhealthy.
*   **Rationale:** Integration tests (like those in Ops-Core's `tests/integration/test_real_agentkit_workflow.py`) need a reliable way to determine when the AgentKit service is fully started and ready to accept requests before proceeding with tests. The current lack of a `/health` endpoint causes test setup failures due to timeouts (observed 404 errors when polling `/health`). While the root `/` endpoint exists, `/health` is a more standard convention.
*   **Implementation Pointer:** Add a new route handler function decorated with `@app.get("/health")` in `agentkit/main.py`.

### 2.2. Fix Webhook Payload Serialization

*   **Requirement:** Correct the serialization of the agent registration details payload before sending it via webhook to Ops-Core.
*   **Issue:** When an agent registers, the background task attempting to notify Ops-Core via webhook fails with `TypeError: Object of type AgentMetadata is not JSON serializable`.
*   **Location:** The error occurs within the `notify_opscore_webhook` function (or similar background task logic triggered) in `agentkit/api/endpoints/registration.py` during the `json.dumps(payload)` call.
*   **Cause:** The `payload` dictionary being serialized contains an `AgentMetadata` object (likely within the `agent_details` sub-dictionary), which is not directly serializable by the standard `json` library.
*   **Required Fix:** Before calling `json.dumps`, ensure all objects within the `payload` are JSON-serializable types (strings, numbers, lists, dictionaries, booleans, None). Specifically, the `AgentMetadata` object needs to be converted to a dictionary representation. If `AgentMetadata` is a Pydantic model, calling `.model_dump()` (or `.dict()` in Pydantic v1) on the instance before adding it to the payload dictionary might resolve this.
*   **Rationale:** This error prevents Ops-Core from receiving agent registration notifications via the webhook, breaking a key part of the integration flow and causing subsequent test steps (like verifying agent registration in Ops-Core) to fail.
*   **Implementation Pointer:** Modify the construction of the `payload` dictionary within the webhook sending logic in `agentkit/api/endpoints/registration.py` to ensure proper serialization of the `agent_details`, particularly the metadata part.

## 3. Conclusion

Addressing these two points (adding a `/health` endpoint and fixing the webhook serialization) is crucial for enabling robust integration testing and ensuring reliable communication between AgentKit and Ops-Core.