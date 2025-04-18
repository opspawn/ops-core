# AgentKit Requirements for Ops-Core Integration

This document tracks features and API specifications required from the AgentKit service for seamless integration with Ops-Core.

## 1. Agent Discovery/Registration Webhooks (Required for Task 3.4 - Webhook Approach)

*   **Requirement:** AgentKit needs the capability to send webhook notifications (HTTP POST) to a configurable Ops-Core endpoint upon agent registration and deregistration events.
*   **Trigger:** Agent registration (e.g., via `POST /v1/agents`) or deregistration (if applicable).
*   **Target Endpoint (Ops-Core):** Configurable URL provided to AgentKit (e.g., via environment variable or configuration). Ops-Core will expose an endpoint like `POST /v1/opscore/internal/agent/notify`.
*   **Payload:** The webhook payload should contain:
    *   `event_type`: String (e.g., "REGISTER", "DEREGISTER").
    *   `agent_details`: Object containing necessary agent information (e.g., `agent_id`, `name`, `capabilities`, etc. - exact fields TBD based on `Agent` model).
*   **Status:** Pending implementation/confirmation in the real AgentKit service. Mock implementation will simulate this.