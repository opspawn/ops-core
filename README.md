# Opspawn Core (`ops-core`)

## Overview

`ops-core` is the orchestration engine component of the Opspawn Core Foundation project. It is responsible for managing task execution, scheduling, state tracking, and workflow coordination for AI agents, particularly those built using the accompanying `agentkit` library.

## Key Features

-   **Task Scheduling:** Manages job queuing, prioritization, and execution. Currently uses Dramatiq with RabbitMQ for asynchronous task handling.
-   **Metadata Store:** Tracks task states, definitions, and execution history (currently using an in-memory store for MVP).
-   **API Interface:** Provides REST (FastAPI) and gRPC endpoints for task submission, status querying, and management.
-   **MCP Integration:** Acts as the central MCP Host/Client, managing connections to external MCP Servers and injecting a proxy tool into agents for controlled external access.
-   **Integration with `agentkit`:** Designed to orchestrate agents built with `agentkit`.

## Getting Started

*(Instructions for setup, running tests, and starting the service will be added here)*

## Project Structure

-   `ops_core/`: Main source code directory.
    -   `api/`: FastAPI application, endpoints, and schemas.
    -   `config/`: Configuration loading (e.g., MCP servers).
    -   `grpc_internal/`: gRPC servicer implementation and generated code.
    -   `mcp_client/`: Client for interacting with MCP servers.
    -   `metadata/`: Task state storage logic.
    -   `models/`: Pydantic data models (e.g., Task).
    -   `proto/`: Protocol Buffer definitions.
    -   `scheduler/`: Task scheduling and agent execution logic.
    -   `tasks/`: Asynchronous task broker and worker setup (Dramatiq).
-   `tests/`: Pytest unit and integration tests.
-   `load_tests/`: Locust load testing scripts.
-   `pyproject.toml`: Project metadata and dependencies.
-   `tox.ini`: Test automation configuration.

## Contributing

*(Contribution guidelines will be added here)*
