# Current Task Plan

**I. Goal:**

To create a robust and well-integrated Ops-Core system that effectively manages AI agent lifecycles and workflows within the Opspawn ecosystem.

**II. Principles:**

*   Prioritize Integration: Focus on seamless integration with AgentKit.
*   Test-Driven Development: Write tests before or alongside code.
*   Iterative Development: Break down tasks into smaller, manageable chunks.
*   Clear Documentation: Document all code and configurations.

**III. Phases:**

1.  **AgentKit Integration (Focus First):**
    *   **A. Mock AgentKit Integration (Docker):**
        *   Create a `docker-compose.yml` file with `opscore` and a mock `agentkit` service.
        *   Implement the necessary AgentKit endpoints in the mock service (`GET /v1/agents`, `POST /v1/agents/{agentId}/run`).
            *   Use the information in `agentkit_integration_for_opscore.md` to implement these endpoints correctly.
        *   Configure Ops-Core to use the mock AgentKit API (likely through environment variables).
        *   Write integration tests to verify basic interactions (agent registration, task dispatch).
    *   **B. Real AgentKit Integration:**
        *   Configure Ops-Core to point to the real AgentKit API.
        *   Test the integration thoroughly, addressing any compatibility issues.
        *   Confirm the `GET /v1/agents` endpoint details with the AgentKit team.
            *   The `agentkit_integration_for_opscore.md` file indicates that this endpoint needs to be confirmed or implemented in AgentKit.

2.  **Python SDK Development (After AgentKit Integration):**
    *   **A. SDK Structure:**
        *   Create an `opscore_sdk` directory with `__init__.py`, `client.py`, `models.py`, and `exceptions.py`.
    *   **B. `OpsCoreClient` Class:**
        *   Implement methods for interacting with the Ops-Core API (register agent, update state, trigger workflow, etc.).
        *   Use the `requests` library for HTTP requests.
    *   **C. Models and Exceptions:**
        *   Copy Pydantic models from `opscore/models.py` to `opscore_sdk/models.py`.
        *   Create custom exceptions in `opscore_sdk/exceptions.py`.
    *   **D. Error Handling and Logging:**
        *   Implement robust error handling in the `OpsCoreClient` methods.
        *   Use the `logging` module for logging.

3.  **Testing and Validation:**
    *   **A. Unit Tests:**
        *   Write unit tests for all core modules (lifecycle, workflow, storage, API).
        *   Aim for high test coverage (80% or higher).
    *   **B. Integration Tests:**
        *   Develop integration tests that simulate complete workflows.
        *   Test the SDK against both the mock and real AgentKit APIs.
    *   **C. CI/CD:**
        *   Set up GitHub Actions for automated testing, linting, and code style enforcement.

4.  **Documentation and Finalization:**
    *   **A. Developer README:**
        *   Update the `README.md` with detailed instructions for installation, configuration, and usage.
    *   **B. API Documentation:**
        *   Generate interactive API documentation using Swagger/OpenAPI.
    *   **C. Sample Projects and Tutorials:**
        *   Create sample projects and tutorials illustrating how to integrate Ops-Core with AgentKit.

**IV. Task Prioritization:**

Based on the current `TASK.md` and the above plan, here's a prioritized list of tasks:

1.  **Task 3.4:** Ensure all endpoints interoperate seamlessly with AgentKit’s integration interfaces. (This is the highest priority, as it enables the rest of the system.)
    *   Implement the mock AgentKit API in a Docker environment.
    *   Configure Ops-Core to use the mock AgentKit API.
    *   Write integration tests to verify basic interactions.
2.  **Task 4.2:** Develop integration tests simulating complete workflows (e.g., agent registration → state update → workflow execution). (Crucial for verifying the AgentKit integration.)
3.  **Task 3.1:** Integrate the Ops‑Core API endpoints with a Python SDK. (Develop the SDK after the AgentKit integration is stable.)
4.  **Task 3.2:** Create a simple CLI application to interact with Ops‑Core endpoints. (Useful for manual testing and demonstration.)
5.  **Task 3.3:** Implement middleware for structured logging and standardized error handling across endpoints. (Improves the robustness and maintainability of the API.)
6.  **Task 2.9:** Develop a basic CLI or web dashboard for real‑time log inspection and filtering. (Provides valuable debugging tools.)
7.  **Task 2.10:** Incorporate performance tracing methods like `startTrace(taskId)` and `endTrace(taskId)`. (Helps identify performance bottlenecks.)
8.  **Task 4.3:** Set up GitHub Actions to automatically run tests, enforce linting, and maintain code style. (Ensures code quality and consistency.)
9.  **Task 4.4:** Perform performance and load testing on API endpoints to gauge response times. (Identifies performance limitations.)
10. **Task 4.5:** Conduct User Acceptance Testing (UAT) with internal scenarios and sample use cases. (Validates the system with real-world scenarios.)
11. **Task 5.1 - 5.5:** Documentation and Finalization tasks. (Complete these after the core functionality is stable.)

**V. Key Information from `agentkit_integration_for_opscore.md`:**

*   **Agent Registration Data:**
    *   Ops-Core should periodically poll AgentKit's `GET /v1/agents` endpoint to discover registered agents and synchronize metadata.
    *   Expected Response Format: (See the example in the file)
*   **Dispatching Tasks/Messages to Agents:**
    *   Ops-Core must dispatch tasks or commands to specific agents by sending a POST request to AgentKit's central messaging endpoint: `POST /v1/agents/{agentId}/run`.
    *   Required Request Payload: (See the example in the file)
*   **Receiving Agent State Updates:**
    *   Ops-Core must implement and expose a dedicated API endpoint to receive direct state updates from AgentKit agents: `POST /v1/opscore/agent/{agentId}/state`.
    *   Expected Request Payload: (See the example in the file)
    *   Authentication: Ops-Core's `/state` endpoint must implement authentication. The AgentKit SDK sends an API key in the `Authorization` header as a Bearer token.
    *   Expected Header: `Authorization: Bearer <OPSCORE_API_KEY_value>`

**VI. Mermaid Diagram:**

```mermaid
graph TD
    A[AgentKit Integration (Mock)] --> B(AgentKit Integration (Real));
    B --> C(Python SDK Development);
    C --> D(Testing and Validation);
    D --> E(Documentation and Finalization);