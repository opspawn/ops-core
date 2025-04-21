# Task 4.4: Performance and Load Testing Plan

**Objective:** To understand the performance characteristics, scalability limits, and potential bottlenecks of the critical Ops-Core API endpoints under various load conditions, using Locust.

**Tool:** Locust (Python-based load testing tool)

**Target Environment:** Ops-Core service running in the Docker environment defined by `docker-compose.real-agentkit.yml` (includes Redis backend).

**Target API Endpoints:**

*   `POST /v1/opscore/agent/{agentId}/state`: For simulating agent state updates.
*   `POST /v1/opscore/agent/{agentId}/workflow`: For simulating workflow initiation.
*   `GET /v1/opscore/agent/{agentId}/state`: For simulating agent state monitoring.

**Testing Scenarios:**

We will execute five distinct scenarios to cover different load patterns:

0.  **Scenario 0: Minimal Load Test (Initial Check)**
    *   **Purpose:** Verify that the load testing environment (Locust, Ops-Core, Redis) is set up correctly and that basic requests are processed without errors under minimal load. This is a quick check before running more extensive tests.
    *   **Endpoint(s):** `POST /v1/opscore/agent/{agentId}/state` (or a simple mix)
    *   **Load Profile:**
        *   Ramp-up: Start with 1 concurrent user and increase to 5 concurrent users over 1 minute.
        *   Steady State: Maintain 5 concurrent users.
        *   Request Rate: Each user sends a request every 1 to 2 seconds.
    *   **Duration:** 5 minutes total.
    *   **Key Metrics:** Success rate (should be 100%), basic response times, no errors in logs.

1.  **Scenario 1: High State Update Load**
    *   **Purpose:** Test the system's ability to handle a large volume of frequent state updates, focusing on the `POST /v1/opscore/agent/{agentId}/state` endpoint and the underlying storage performance.
    *   **Endpoint(s):** `POST /v1/opscore/agent/{agentId}/state`
    *   **Load Profile:**
        *   Ramp-up: Start with 10 concurrent users and increase to 500 concurrent users over 5 minutes.
        *   Steady State: Maintain 500 concurrent users.
        *   Request Rate: Each user sends a state update request every 5 to 10 seconds.
    *   **Duration:** 15 minutes at peak load.
    *   **Key Metrics:** RPS for `/state`, response times for `/state`, CPU/Memory usage of `opscore` and `redis` containers.

2.  **Scenario 2: Workflow Initiation Load**
    *   **Purpose:** Test the system's capacity to handle requests for starting new workflows, focusing on the `POST /v1/opscore/agent/{agentId}/workflow` endpoint and the workflow engine's initiation logic.
    *   **Endpoint(s):** `POST /v1/opscore/agent/{agentId}/workflow`
    *   **Load Profile:**
        *   Ramp-up: Start with 10 concurrent users and increase to 100 concurrent users over 3 minutes.
        *   Steady State: Maintain 100 concurrent users.
        *   Request Rate: Each user triggers a workflow every 30 to 60 seconds. (Requires a sample workflow definition).
    *   **Duration:** 15 minutes at peak load.
    *   **Key Metrics:** RPS for `/workflow`, response times for `/workflow`, CPU/Memory usage of `opscore` container.

3.  **Scenario 3: Mixed Realistic Load**
    *   **Purpose:** Simulate a more typical production workload with a mix of state updates, workflow triggers, and state monitoring requests.
    *   **Endpoint(s) & Weighting:**
        *   `POST /v1/opscore/agent/{agentId}/state`: 80% of requests
        *   `GET /v1/opscore/agent/{agentId}/state`: 15% of requests
        *   `POST /v1/opscore/agent/{agentId}/workflow`: 5% of requests
    *   **Load Profile:**
        *   Ramp-up: Start with 20 concurrent users and increase to 300 concurrent users over 5 minutes.
        *   Steady State: Maintain 300 concurrent users with request distribution based on weighting.
    *   **Duration:** 30 minutes at peak load.
    *   **Key Metrics:** Overall RPS, individual endpoint RPS, response times for all endpoints, CPU/Memory usage of `opscore` and `redis` containers, error rates.

4.  **Scenario 4: Stress Test**
    *   **Purpose:** Identify the system's breaking point, maximum sustainable load, and primary bottlenecks under extreme conditions.
    *   **Endpoint(s):** Mixed load (same weighting as Scenario 3).
    *   **Load Profile:**
        *   Start: Begin with the peak load of Scenario 3 (300 concurrent users).
        *   Ramp-up: Incrementally increase the number of concurrent users by 50 every 5 minutes.
    *   **Duration:** Continue until average response times for critical endpoints exceed 2 seconds or the overall error rate surpasses 5%.
    *   **Key Metrics:** Maximum sustainable RPS, load level at failure, response time trends, error rate trends, resource utilization at failure point.

**Metrics to Collect:**

*   **Locust Output:** RPS (overall and per endpoint), Response Times (Average, Median, 90th, 95th, 99th percentile), Failure Rate (%), Number of Concurrent Users.
*   **System Monitoring:** CPU Utilization (%), Memory Usage (MB/GB), Network I/O for `opscore` and `redis` Docker containers (using `docker stats` or similar tools).
*   **Application Logs:** Ops-Core application logs for errors, warnings, or performance-related messages.

**Implementation Steps:**

1.  **Environment Setup:**
    *   Ensure the Python virtual environment is activated (`./.venv/bin/python`).
    *   Ensure Locust is installed (`pip install locust`).
    *   Stop any currently running Docker containers that might conflict.
    *   Start the Ops-Core and Redis services using `docker-compose -f docker-compose.real-agentkit.yml up --build -d`.
    *   Identify the base URL for the Ops-Core API (likely `http://localhost:8000` or the service name within the Docker network if running Locust from another container).
    *   Make the Ops-Core API Key available to the Locust test script (e.g., via environment variables).
    *   Prepare a sample workflow definition file (e.g., `sample_workflow.json`) for Scenario 2 and 3.

2.  **Create Locustfile:**
    *   Create a Python file (e.g., `load_tests/opscore_locustfile.py`) that defines the load test using Locust's API.
    *   Implement a `User` class that inherits from `HttpUser`.
    *   Define tasks within the `User` class using the `@task` decorator for each target endpoint (`POST /state`, `GET /state`, `POST /workflow`).
    *   Implement logic to handle API Key authentication (e.g., setting a default header).
    *   Implement logic to generate or select dynamic `agentId` values for requests.
    *   Create realistic request payloads for each endpoint based on the Ops-Core API schema.
    *   Use the `@task` decorator with weights to define the request distribution for mixed scenarios.

3.  **Execute Tests:**
    *   Run Locust from the terminal using the created locustfile: `locust -f load_tests/opscore_locustfile.py`.
    *   Use the Locust web UI (usually at `http://localhost:8089`) to configure and start each scenario with the specified load profiles (number of users, spawn rate, duration).
    *   Alternatively, run Locust in headless mode from the CLI for automated execution.

4.  **Monitor and Collect Data:**
    *   Observe the Locust web UI for real-time statistics (RPS, response times, failures).
    *   Use `docker stats opscore redis` in a separate terminal to monitor container resource usage during the tests.
    *   Review Ops-Core application logs for any errors or exceptions.

5.  **Analyze Results:**
    *   Review the collected metrics from Locust and system monitoring.
    *   Identify peak performance (RPS) for each scenario.
    *   Analyze how response times change as load increases.
    *   Look for correlations between performance degradation and resource utilization (CPU, Memory).
    *   Identify any endpoints or operations that are significantly slower or have higher error rates.
    *   Determine the load level at which the system begins to fail or degrade unacceptably (from the stress test).

6.  **Document Findings:**
    *   Summarize the results of each test scenario.
    *   Document the observed performance limits and bottlenecks.
    *   Provide recommendations for potential optimizations (e.g., code improvements, Redis configuration tuning, scaling strategies).
    *   Update `TASK.md` to mark Task 4.4 as completed and summarize the outcome.
    *   Update relevant memory-bank files (`activeContext.md`, `progress.md`, potentially `systemPatterns.md` or `techContext.md` if significant insights are gained).