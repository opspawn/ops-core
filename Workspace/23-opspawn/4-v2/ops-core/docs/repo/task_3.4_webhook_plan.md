# Plan: Task 3.4 - AgentKit Integration Enhancements (Webhook Approach)

## Objective
Continue Task 3.4: Ensure all endpoints interoperate seamlessly with AgentKit’s integration interfaces. Focus on implementing agent discovery via webhooks and expanding integration tests to cover workflow scenarios involving state updates from the mock agent back to Ops-Core.

## Part 1: Implement Agent Discovery & Registration via Webhooks

1.  **Ops-Core Webhook Endpoint:**
    *   Define a new internal API endpoint in `opscore/api.py`, e.g., `POST /v1/opscore/internal/agent/notify`.
    *   Accepts payload from AgentKit: agent details + event type (`REGISTER`, `DEREGISTER`).
    *   Handler calls `opscore.lifecycle.register_agent` or `deregister_agent`.
    *   **Security Note:** Consider future hardening for this internal endpoint. Assume Docker network access for now.
2.  **Mock AgentKit Webhook Simulation:**
    *   Modify `mock_agentkit/main.py`.
    *   On `POST /v1/agents`, trigger HTTP POST to Ops-Core's webhook (`http://opscore_service:8000/v1/opscore/internal/agent/notify`) with agent details and `REGISTER` type.
    *   (Optional) Implement `DEREGISTER` notification if agent removal is added to mock.
3.  **Ops-Core Startup:** No polling needed; registration is event-driven.

## Part 2: Expand Integration Tests for Agent State Updates

*   Add new async tests to `tests/test_agentkit_integration.py`.
*   **Test Flow Simulation:**
    *   **Setup:** Trigger mock AgentKit registration (`POST /v1/agents`) -> AgentKit notifies Ops-Core via webhook.
    *   **Dispatch:** Ops-Core dispatches task to mock AgentKit (`POST /v1/agents/{agentId}/run`).
    *   **Mock Agent Action:** Mock AgentKit simulates processing -> Calls back Ops-Core state update (`POST /v1/opscore/agent/{agentId}/state`).
    *   **Verification:** Assert Ops-Core `LifecycleManager` reflects correct state changes.
*   **Visualization:**
    ```mermaid
    sequenceDiagram
        participant TestClient
        participant MockAgentKitAPI
        participant OpsCoreAPI
        participant OpsCoreLifecycle

        TestClient->>MockAgentKitAPI: POST /v1/agents (Register Agent)
        MockAgentKitAPI->>OpsCoreAPI: POST /v1/opscore/internal/agent/notify (REGISTER)
        OpsCoreAPI->>OpsCoreLifecycle: Register Agent

        TestClient->>OpsCoreAPI: Dispatch Task (e.g., via Workflow Trigger)
        OpsCoreAPI->>MockAgentKitAPI: POST /v1/agents/{agentId}/run
        MockAgentKitAPI->>OpsCoreAPI: POST /v1/opscore/agent/{agentId}/state (e.g., state=BUSY)
        OpsCoreAPI->>OpsCoreLifecycle: Update Agent State
        MockAgentKitAPI->>OpsCoreAPI: POST /v1/opscore/agent/{agentId}/state (e.g., state=IDLE)
        OpsCoreAPI->>OpsCoreLifecycle: Update Agent State
        TestClient->>OpsCoreAPI: GET /v1/opscore/agent/{agentId}/state (or internal check)
        OpsCoreAPI->>TestClient: Return Final State (IDLE)
        Note over TestClient, OpsCoreLifecycle: Test asserts final state is IDLE
    ```

## Part 3: Track Requirements for Real AgentKit

*   Maintain a running list in `AGENTKIT_REQUIREMENTS.md`.
*   **Initial Item:** AgentKit needs capability to send webhook notifications (HTTP POST) to a configurable Ops-Core endpoint upon agent registration/deregistration events. Payload: agent details + event type.

## Considerations
*   `docker-compose up --build` must remain running.
*   Integration depends on mock AgentKit; real integration needs confirmed AgentKit API specs.