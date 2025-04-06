dd# Active Context: Opspawn Core Foundation (Phase 2 In Progress)

## Current Focus
- **Phase 2: Core Module Development:** Continuing development of core components.
- **Task 2.3: Develop Agentkit Dynamic Tool Integration:** Starting work on integrating dynamic tools into `agentkit`.

## Recent Activities (Current Session)
- Completed Phase 1 (Tasks 1.1 - 1.4).
- **Completed Task 2.1:**
    - Implemented `ops_core/models/tasks.py` (Pydantic models, timezone-aware).
    - Implemented `ops_core/metadata/store.py` (`InMemoryMetadataStore` with CRUD methods).
    - Implemented `ops_core/scheduler/engine.py` (`InMemoryScheduler` interacting with store).
    - Added `pytest`, `pydantic` to `ops-core/requirements.txt`.
    - Created and passed unit tests for store and scheduler (`tests/test_metadata_store.py`, `tests/test_scheduler_engine.py`).
    - Committed and pushed changes to `ops-core` repository.
    - Updated `23-opspawn/TASK.md` to mark Task 2.1 complete.
- **Completed Task 2.2:**
    - Created `agentkit` package structure (`agentkit/agentkit/`, `agentkit/tests/`).
    - Implemented `agentkit/memory/short_term.py` (`ShortTermMemory` class).
    - Implemented `agentkit/planning/simple_planner.py` (placeholder `SimplePlanner` class).
    - Implemented `agentkit/core/agent.py` (core `Agent` class integrating memory/planner).
    - Added basic unit tests (`tests/test_memory.py`, `tests/test_planning.py`, `tests/test_agent.py`).
    - Added `pytest` to `agentkit/requirements.txt`.
    - Committed changes to `agentkit` repository.
- **Started Task 2.3:**
    - Created `agentkit/tools/` directory.
    - Implemented `agentkit/tools/schemas.py` (ToolSpec, ToolResult using Pydantic).
    - Implemented `agentkit/tools/registry.py` (Tool, ToolRegistry, error classes).
    - Added `__init__.py` to `agentkit/tools/`.
    - Integrated `ToolRegistry` into `agentkit/core/agent.py` (init, context, execution loop).
    - Added `pydantic`, `pytest-asyncio` to `agentkit/requirements.txt`.
    - Created `agentkit/tests/test_tools.py` with comprehensive unit tests.
    - Updated `agentkit/tests/test_agent.py` to reflect changes in agent execution flow and memory updates.
    - Ran all `agentkit` tests successfully.
    - Committed changes to `agentkit` repository.
    - Updated `TASK.md` to mark Task 2.3 as "In Progress".
- Reviewed all project documentation and Memory Bank files at the start of the session.

## Key Research Takeaways & Design Principles (Consolidated)
- **`agentkit`:**
    - Adopt "core-agent" pattern (Planning, Memory, Profile, Action, Security modules).
    - Prioritize modularity and composability (pluggable components).
    - Support diverse memory types (short-term context, long-term vector stores).
    - Implement dynamic, secure tool integration (sandboxing essential).
    - Utilize `asyncio` for non-blocking operations.
- **`ops-core`:**
    - Implement robust scheduling (hybrid/shared-state inspired?) with clear Scheduler/Worker separation.
    - Use a persistent metadata store (SQL DB) for state tracking and reliability.
    - Be API-driven (REST external, gRPC internal recommended for performance).
    - Build-in observability (logging, monitoring).
    - Consider event-driven patterns for decoupling/scaling if needed.
- **Integration:**
    - Define clear API contracts early (OpenAPI for REST, Protobuf for gRPC).
    - Support both sync and async communication patterns.
- **Documentation:**
    - Use Diátaxis structure (Tutorials, How-Tos, Explanations, Reference).
    - Employ docs-as-code (Sphinx/MkDocs).
    - Document decisions via ADRs.

## Immediate Next Steps
1.  **Continue Task 2.3:** Develop Agentkit Dynamic Tool Integration.
    - Define clear interfaces/protocols for how tools should be implemented (e.g., base class, function signature requirements).
    - Implement basic security considerations (e.g., input validation is done, consider function call safety, potential sandboxing research).
    - Refine tool execution logic in `Agent` if needed (e.g., better error handling, memory updates).
2.  **Start MCP Integration (Phase 3.5):** Begin work on the MCP integration tasks, starting with Task MCP.1 (Implement `ops-core` MCP Client Module).
3.  **Start Task 2.4:** Define & Implement Internal Interfaces for Agentkit Modules once Task 2.3 is sufficiently complete.

## Active Decisions & Considerations
- **MCP Integration Strategy:** Decided to use the **Dynamic Proxy Pattern**, where `ops-core` acts as the MCP Host/Client and injects a proxy tool into `agentkit` agents for controlled external access (Decision Date: 2025-04-05).
- The primary workspace is `/home/sf2/Workspace/23-opspawn`. All project-related work should occur relative to this directory unless specified otherwise. (Corrected path based on initial prompt).
- Adherence to `.clinerules/project-guidelines.md` is mandatory.
