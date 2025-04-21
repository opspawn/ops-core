# Plan to Fix Task 4.2 (401 Unauthorized Error)

## Objective
Resolve the `401 Unauthorized` error currently blocking **Task 4.2 (Real AgentKit Integration Tests)**. This error occurs when the integration test (`tests/integration/test_real_agentkit_workflow.py`) attempts to poll the Ops-Core API endpoint `/v1/opscore/agent/{agentId}/state`. The root cause is the `opscore_client` fixture in `tests/conftest.py` sending the API key using an incorrect header format (`X-API-Key`) instead of the required `Authorization: Bearer <key>` format.

## Plan Steps

1.  **Modify Test Fixture:**
    *   Target File: `tests/conftest.py`
    *   Target Fixture: `opscore_client`
    *   Action: Update the fixture to correctly construct the `httpx.AsyncClient`. Specifically, ensure it retrieves the API key from the `OPSCORE_API_KEY` environment variable and sets the `Authorization` header in the format `Bearer <key>`.

    ```mermaid
    graph TD
        A[Read tests/conftest.py] --> B{Locate opscore_client fixture};
        B --> C[Get OPSCORE_API_KEY env var];
        C --> D[Construct 'Authorization: Bearer <key>' header];
        D --> E[Instantiate httpx.AsyncClient with correct header];
        E --> F[Yield Client];
    ```

2.  **Verify Fix:**
    *   Command: Run the specific integration test using the virtual environment's Python interpreter:
        ```bash
        ./.venv/bin/python -m pytest tests/integration/test_real_agentkit_workflow.py
        ```
    *   Expected Outcome: The test should proceed past the API polling step without encountering the `401 Unauthorized` error. (Note: The test might still fail later due to the original `idle` state timeout issue, which is the next debugging step).

3.  **Proceed with Task 4.2:**
    *   If the 401 error is resolved, continue debugging the underlying issue where the test times out waiting for the agent state to become `idle` via the API, as detailed in `memory-bank/activeContext.md`.

## Next Action
After this plan is written to the file, I will request to switch to `code` mode to implement the fix in `tests/conftest.py`.