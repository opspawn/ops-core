# Product Context: Ops-Core Python Module

## 1. Why This Project Exists
Opspawn aims to simplify the development, deployment, and management of complex AI agent systems. As agent interactions become more sophisticated (multi-step workflows, inter-agent communication), a dedicated system is needed to manage their operational state and coordinate their activities reliably. AgentKit provides the tools to build agents, but lacks robust orchestration and lifecycle management capabilities for complex, potentially long-running tasks. Ops-Core fills this gap.

## 2. Problems It Solves
- **Lack of Centralized Orchestration:** Managing multiple agents, their states, and the sequence of tasks across them is complex and error-prone without a dedicated system.
- **State Management Complexity:** Tracking the operational state (e.g., idle, busy, error) of numerous agents consistently is challenging.
- **Workflow Coordination:** Defining, executing, and monitoring multi-step workflows involving one or more agents requires a structured approach.
- **Debugging Difficulty:** Understanding failures and performance bottlenecks in distributed agent systems is difficult without centralized logging and tracing.
- **Integration Overhead:** Providing a standardized way for agents (built with tools like AgentKit) to report status and receive tasks reduces boilerplate code for agent developers.

## 3. How It Should Work (User Perspective - Primarily Developers)
- **Simplified Agent Management:** Developers using Opspawn should be able to easily monitor the status and lifecycle of their registered agents through Ops-Core.
- **Declarative Workflows:** Developers should define complex agent interactions using simple, declarative templates (JSON/YAML) that Ops-Core executes.
- **Reliable Task Execution:** Ops-Core should reliably dispatch tasks to the correct agents (via AgentKit) and manage basic error handling/retries.
- **Transparent Operations:** Developers need clear visibility into agent activities and workflow progress through accessible logs and debugging information provided by Ops-Core.
- **Seamless Integration:** Agents built with the AgentKit SDK should automatically report their state to Ops-Core with minimal configuration (`OPSCORE_API_URL`, `OPSCORE_API_KEY`). Ops-Core should handle task dispatching via AgentKit's established routing mechanisms.

## 4. User Experience Goals
- **Developer Productivity:** Reduce the complexity and time required to build, deploy, and manage multi-agent systems.
- **Reliability & Trust:** Provide a stable and predictable operational layer that developers can rely on for agent orchestration.
- **Visibility & Control:** Offer clear insights into system operations and provide mechanisms to manage workflows and agent states.
- **Scalability:** Design with future scaling in mind, even if the initial implementation is local-first.