# System Patterns: Ops-Core Python Module

## 1. System Architecture Overview
Ops-Core is designed as a modular Python service acting as the central nervous system for agent operations within the Opspawn ecosystem. It interacts primarily with AgentKit (for agent discovery and task dispatch) and directly with agents (via the AgentKit SDK for state reporting).

```mermaid
graph LR
    subgraph Ops-Core Module
        direction LR
        API[API Layer (FastAPI)]
        LM[Lifecycle Management]
        WS[Workflow Sequencing]
        LOG[Logging/Debugging]
        STORE[Storage (In-Memory)]
    end

    subgraph AgentKit
        direction LR
        AK_API[AgentKit API]
        AK_SDK[AgentKit SDK]
        AGENT[Agent Process]
    end

    API -- Manages --> LM;
    API -- Triggers --> WS;
    API -- Receives State Updates --> LM;
    LM -- Uses --> STORE;
    WS -- Uses --> STORE;
    WS -- Dispatches Tasks via --> AK_API;
    LOG -- Used by --> API;
    LOG -- Used by --> LM;
    LOG -- Used by --> WS;

    AK_API -- Routes Tasks --> AGENT;
    AGENT -- Uses --> AK_SDK;
    AK_SDK -- Reports State --> API;
    API -- Polls Agent Info --> AK_API;

    style Ops-Core Module fill:#f9f,stroke:#333,stroke-width:2px
    style AgentKit fill:#ccf,stroke:#333,stroke-width:2px
```

## 2. Key Technical Decisions
- **Language:** Python 3.9+ (Chosen for its strong ecosystem in AI/ML and web development).
- **Web Framework:** FastAPI (Chosen for performance, automatic OpenAPI documentation, type hinting integration via Pydantic, and asynchronous support potential).
- **Initial Storage:** In-memory Python dictionaries (Chosen for simplicity in local-first development and MVP phase. Planned migration to persistent storage like Redis or a DB).
- **Communication Protocols:**
    - RESTful APIs (JSON over HTTP/S) for interactions between Ops-Core, AgentKit, and Agents (via SDK).
    - Standardized JSON schemas for API request/response validation.
- **Logging:** Structured JSON logging using Python's standard `logging` module (Facilitates parsing and future integration with log aggregation systems).
- **Testing:** Pytest (Standard Python testing framework).
- **Containerization:** Docker/Docker Compose (For reproducible development and testing environments).
- **Authentication:** API Key (Bearer Token) for initial security between AgentKit SDK and Ops-Core API.

## 3. Design Patterns & Approaches
- **Modular Design:** Core functionalities (Lifecycle, Workflow, Logging, API) are separated into distinct Python modules/subsystems.
- **Centralized State Management:** Ops-Core acts as the source of truth for agent operational states and workflow progress.
- **Declarative Workflows:** Workflows are defined externally (JSON/YAML) rather than hardcoded, allowing flexibility.
- **API Gateway Pattern (Simplified):** The FastAPI application serves as the single entry point for external interactions with Ops-Core.
- **Repository Pattern (Conceptual):** The `storage.py` module will abstract data storage/retrieval logic, initially for in-memory data, allowing easier replacement later.
- **Observer Pattern (Implicit):** Agents (via SDK) "notify" Ops-Core of state changes.

## 4. Component Relationships & Interactions
- **Ops-Core API <-> AgentKit SDK:** Receives agent state updates (`POST /v1/opscore/agent/{agentId}/state`) authenticated via API Key.
- **Ops-Core API <-> AgentKit API:**
    - Polls for registered agent information (`GET /v1/agents` - TBC).
    - Dispatches tasks to specific agents (`POST /v1/agents/{agentId}/run`).
- **Internal Ops-Core:**
    - API layer delegates requests to Lifecycle Management and Workflow Sequencing subsystems.
    - Lifecycle and Workflow subsystems use the Storage module for persistence.
    - All subsystems utilize the Logging module.

## 5. Critical Implementation Paths
- **State Update Endpoint:** Securely receiving, validating, and processing state updates from potentially many agents is critical for system accuracy. Authentication and schema validation are paramount.
- **Task Dispatching:** Reliably sending tasks to the correct agent via AgentKit's routing mechanism.
- **Workflow Engine:** Parsing workflow templates and managing the task queue correctly.
- **Agent Discovery:** Keeping the list of known agents synchronized with AgentKit.