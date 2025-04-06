# System Patterns: Opspawn Core Foundation

## 1. Overall Architecture

Opspawn Core Foundation follows a modular, service-oriented architecture consisting of two primary components:

-   **`agentkit`**: A toolkit/library for building LLM-powered agents. Designed to be modular and extensible.
-   **`ops-core`**: An orchestration engine responsible for scheduling, managing, and monitoring agent tasks and workflows.

These components will interact primarily through well-defined APIs.

## 2. `agentkit` Architecture & Patterns

Based on research (LLM-Agent-UMF framework mentioned in `P-RP.txt`), `agentkit` will adopt a "core-agent" paradigm with distinct modules:

-   **Core-Agent Module:** The central coordinator.
    -   **Planning Module:** Decomposes tasks (e.g., using ReAct or Plan-then-Execute patterns) and generates execution steps.
    -   **Memory Module:** Manages agent state, context, and history. Supports short-term (in-context) and long-term (e.g., vector store) memory strategies. Pluggable design for different memory backends.
    -   **Profile Module:** Configures agent behavior, persona, and specific guidelines.
    -   **Action Module:** Executes planned steps, including invoking tools. Standardized interface for tool definition and execution.
    -   **Security Module:** Implements safeguards for tool execution (sandboxing) and potentially communication.
-   **LLM Integration Layer:** Abstract interface to interact with various foundation models (e.g., OpenAI, Anthropic). Handles prompting and response parsing.
-   **Tool Registry & Manager:** System for defining, registering, discovering, and securely invoking external tools (APIs, functions, etc.). Supports dynamic tool use.

**Key Design Patterns:**
-   **Modularity & Composability:** Components designed as pluggable modules with clear interfaces.
-   **Dependency Injection:** Likely used to inject dependencies like LLM clients, memory stores, or tool managers into agents.
-   **Strategy Pattern:** May be used for selecting different planning or memory strategies.
-   **Asynchronous Operations:** Utilize `asyncio` for non-blocking I/O, especially for tool calls and potentially LLM interactions.

## 3. `ops-core` Architecture & Patterns

Based on research comparing orchestration tools (Airflow, Prefect) and scheduler architectures (`P-RP.txt`), `ops-core` will likely adopt a hybrid approach, potentially inspired by shared-state schedulers:

-   **API Gateway:** Primary interface (REST recommended for external, gRPC considered for internal high-performance communication) for submitting tasks, managing workflows, and querying status.
-   **Orchestration Service:** Coordinates workflow execution based on defined logic (potentially DAGs or dynamic flows). Manages task dependencies and state transitions.
-   **Task Scheduling Engine:** Determines when and where tasks (including agent invocations via `agentkit`) should run. Manages job queues, retries, and prioritization.
-   **Execution Engine / Workers:** Executes the actual tasks. Could be distributed and potentially leverage containerization (Docker/Kubernetes) for scalability and isolation.
-   **Metadata Store:** Persistent storage (e.g., PostgreSQL, MySQL) tracking workflow definitions, task states, execution history, and results. Crucial for reliability and recovery.
-   **Monitoring & Logging:** Integrated observability for tracking performance, errors, and system health.

**Key Design Patterns:**
-   **Scheduler/Worker Separation:** Decouples scheduling logic from task execution for scalability and resilience.
-   **Stateful Orchestration:** Maintains persistent state in the metadata store.
-   **Event-Driven Architecture:** Potentially use an internal event bus or message queue (e.g., RabbitMQ, Redis) for asynchronous communication between components (e.g., scheduler dispatching tasks to workers).
-   **API-Driven:** All interactions managed through APIs.
-   **Plugin Architecture:** Consider allowing custom task types or scheduling policies via plugins for extensibility.

## 4. Integration Strategy

-   **Primary Interface:** `ops-core` invokes `agentkit` functionalities (e.g., "run agent task") via a well-defined API.
-   **Protocol:** Start with REST (using FastAPI) for simplicity and external compatibility. Evaluate and potentially implement gRPC for high-throughput internal communication between `ops-core` and `agentkit` if performance requires it.
-   **Data Format:** JSON for REST APIs. Protocol Buffers if gRPC is used.
-   **Communication Style:** Support both synchronous requests (for quick tasks) and asynchronous patterns (e.g., task submission returning a job ID, status polling, or webhooks/callbacks) for long-running agent tasks.
-   **Contracts:** Use OpenAPI specifications for REST APIs and `.proto` definitions for gRPC to ensure clear, versioned contracts.

## 5. Critical Implementation Paths

-   Defining the core API contract between `ops-core` and `agentkit` early is critical.
-   Establishing the structure and interfaces for `agentkit`'s core modules (Memory, Planning, Action).
-   Implementing the basic scheduling loop and state management in `ops-core`.
-   Ensuring secure and reliable tool execution within `agentkit`.
-   Implementing the MCP integration pattern between `ops-core` and `agentkit`.

## 6. MCP Integration Pattern (Dynamic Proxy)

Opspawn integrates with the Model Context Protocol (MCP) using a dynamic proxy pattern to provide agents with controlled access to external tools and data sources.

-   **`ops-core` as Host/Client:** `ops-core` acts as the central MCP Host and Client. It manages connections to external MCP Servers, handles authentication, and enforces policies.
-   **Proxy Tool Injection:** For tasks/agents requiring external access, `ops-core` dynamically injects a special "MCP Proxy Tool" into the `agentkit` agent's internal `ToolRegistry` during initialization.
-   **Agent-Driven Calls:** The `agentkit` agent's planner can generate steps that involve calling this `mcp_proxy_tool`. The agent specifies the target MCP server, tool name, and arguments when calling the proxy.
-   **`ops-core` Execution:** The proxy tool call is routed back to `ops-core`, which then uses its MCP client module to perform the actual communication with the specified external MCP Server.
-   **Result Handling:** `ops-core` receives the response from the MCP Server and returns it to the agent as the result of the proxy tool call.
-   **Benefits:** This pattern maintains a clear separation of concerns (`agentkit` focuses on agent logic, `ops-core` on orchestration and external communication), centralizes control/security/configuration within `ops-core`, and simplifies `agentkit` by abstracting direct MCP communication away from the core agent library.
