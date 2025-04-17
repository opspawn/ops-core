# TASK.md

## Overview
This TASK.md document provides a detailed, step-by-step checklist for developing the Ops‑Core Python module. It is designed to guide the development team through every phase—from initialization and core module development, through integration and testing, to final documentation—ensuring that all aspects of lifecycle management, workflow orchestration, and debugging/logging are fully implemented.

---

## Phases and Task Breakdown

### Phase 1: Initialization & Research [COMPLETED - 2025-04-17]
- [X] **Task 1.1:** Set up a dedicated Git repository and branch structure for the Ops‑Core module. (Internal structure: `opscore/`, `tests/`, `.gitignore`)
  - *Dependency:* Access to the Opsspawn repository.
- [X] **Task 1.2:** Configure the local Python development environment. (Created `requirements.txt`, `venv` is user responsibility)
  - *Steps:* Install Python 3.9+, create virtual environments, and configure IDE settings.
- [X] **Task 1.3:** Create initial Dockerfile and Docker Compose configuration for the Ops‑Core module. (Created `Dockerfile`, `docker-compose.yml`, `.env`)
- [X] **Task 1.4:** Review the Ops‑Core Development document to extract Python-specific requirements. (Done during initial context read)
  - *Reference:* Ops-CoreDevelopmentDoc.md citeturn2file0.
- [X] **Task 1.5:** Document and confirm the Python technology stack and selected tools (FastAPI, pytest, Docker, GitHub Actions). (Confirmed FastAPI, documented in `memory-bank/techContext.md`)

---

### Phase 2: Core Module Development & Refactoring

#### Lifecycle Management Subsystem
- [X] **Task 2.1:** Design and implement a Python function for registering agents. (`opscore/lifecycle.py:register_agent` implemented with UUID, model validation, storage call)
  - *Example Functions:* `registerAgent(agentDetails)` to store metadata and generate a unique agent ID.
- [X] **Task 2.2:** Develop state management functions such as `setState(agentId, newState, details)` and `getState(agentId)`. (`opscore/lifecycle.py:set_state`, `get_state` implemented with storage call)
- [X] **Task 2.3:** Integrate an in‑memory storage solution (`opscore/storage.py` implemented with dicts and locks). [COMPLETED - 2025-04-17]
- [X] **Task 2.4:** Implement session and workflow tracking (`start_session`, `update_session`, `get_session` implemented in `opscore/lifecycle.py` using updated models and storage). [COMPLETED - 2025-04-17]

#### Workflow Sequencing and Orchestration
- [X] **Task 2.5:** Develop a workflow engine using configurable JSON/YAML templates. (`opscore/workflow.py:load_workflow_template`, `create_workflow`, `get_workflow_definition` implemented)
  - *Subtask:* Implement `createWorkflow(workflowTemplate)` and `enqueueTask(taskData)`. (`enqueue_task` implemented with model validation)
- [X] **Task 2.6:** Build a task dispatcher to send tasks to agents based on state and priority. (`opscore/workflow.py:dispatch_task`, `process_next_task` implemented, `scheduleTask` placeholder exists)
  - *Subtask:* Develop `dispatchTask(agentId, task)` and `scheduleTask(task, delay)`.
- [X] **Task 2.7:** Implement error recovery and retry logic placeholders (`handle_task_failure`, `retry_task`, `fallback_task` updated in `opscore/workflow.py`). [COMPLETED - 2025-04-17]

#### Debugging and Logging Subsystem
- [X] **Task 2.8:** Create a centralized logging module to record all critical operations with timestamps and context. (`opscore/logging_config.py` created and integrated into core modules)
  - *Function:* `logOperation(operation, context)` with options for both file-based and console logging. (Basic JSON logging to stdout implemented)
- [ ] **Task 2.9:** Develop a basic CLI or web dashboard for real‑time log inspection and filtering.
- [ ] **Task 2.10:** Incorporate performance tracing methods like `startTrace(taskId)` and `endTrace(taskId)`.

#### Integration Endpoints for AgentKit
 - [X] **Task 2.11:** Develop RESTful API endpoints (using FastAPI) for state updates and workflow triggering. (`/health`, `/v1/opscore/agent/{agentId}/state`, and `/v1/opscore/agent/{agentId}/workflow` implemented in `opscore/api.py`). [COMPLETED - 2025-04-17]
   - *Endpoints:*
     - `POST /v1/opscore/agent/{agentId}/state` for updating agent state. [Implemented]
     - `POST /v1/opscore/agent/{agentId}/workflow` for starting workflows. [Implemented]
- [X] **Task 2.12:** Define and enforce JSON schemas for payloads to ensure input validation. (Pydantic models created in `opscore/models.py`, used in `/state` endpoint and `enqueue_task`)
- [X] **Task 2.13:** Implement API key authentication for each endpoint. (Implemented via FastAPI dependency in `opscore/api.py` for `/state` endpoint)

---

### Phase 3: Integration & Interface Development

- [ ] **Task 3.1:** Integrate the Ops‑Core API endpoints with a Python SDK.
  - *Subtask:* Develop helper functions to simplify API calls (registration, state update, workflow trigger).
- [ ] **Task 3.2:** Create a simple CLI application to interact with Ops‑Core endpoints.
  - *Commands:* Include options for agent registration, state update, and workflow initiation.
- [ ] **Task 3.3:** Implement middleware for structured logging and standardized error handling across endpoints.
- [ ] **Task 3.4:** Ensure all endpoints interoperate seamlessly with AgentKit’s integration interfaces.

---

### Phase 4: Testing & Validation

 - [X] **Task 4.1:** Write unit tests for each subsystem using pytest. (Initial tests for storage, lifecycle, workflow implemented in `tests/`). [COMPLETED - 2025-04-17]
   - *Subtasks:*
     - [X] Validate agent registration with both valid and invalid data.
     - [X] Test state transitions and session tracking.
    - Verify workflow sequencing and error recovery functionalities.
- [ ] **Task 4.2:** Develop integration tests simulating complete workflows (e.g., agent registration → state update → workflow execution).
- [ ] **Task 4.3:** Set up GitHub Actions to automatically run tests, enforce linting, and maintain code style.
- [ ] **Task 4.4:** Perform performance and load testing on API endpoints to gauge response times.
- [ ] **Task 4.5:** Conduct User Acceptance Testing (UAT) with internal scenarios and sample use cases.

---

### Phase 5: Documentation & Finalization

- [ ] **Task 5.1:** Update the Developer README with detailed instructions for installation, configuration, and usage of the Ops‑Core module.
- [ ] **Task 5.2:** Generate interactive API documentation using Swagger/OpenAPI.
- [ ] **Task 5.3:** Create sample projects and tutorials illustrating how to integrate Ops‑Core with AgentKit.
- [ ] **Task 5.4:** Document configuration settings, environment variables, and dependencies in a dedicated configuration guide.
- [ ] **Task 5.5:** Perform a final review and consolidate all project documentation for final integration and future enhancements.

---

## Backlog / Future Enhancements
- [ ] **Task B1:** Implement asynchronous messaging support for improved responsiveness.
- [ ] **Task B2:** Migrate from in‑memory storage to a persistent database solution.
- [ ] **Task B3:** Develop an advanced debugging interface, including a web-based log dashboard.
- [ ] **Task B4:** Enhance security protocols with OAuth/SSO and role‑based access control.
- [ ] **Task B5:** Optimize workflow orchestration with machine learning–driven performance adjustments.
- [ ] **Task B6:** Expand API endpoints to support additional third-party tool integrations.

---

## Final Thoughts
This TASK.md document represents the detailed, actionable checklist required for building the Ops‑Core Python module. Covering each phase from initial setup and core module development through integration, rigorous testing, and final documentation, it serves as a living guide to keep the development process organized and aligned with the long-term Opsspawn vision.