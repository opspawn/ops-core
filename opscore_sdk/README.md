# Ops-Core Python SDK

This SDK provides Python clients for interacting with the Ops-Core API.

## Installation

```bash
# Assuming httpx is added to your project's requirements
pip install httpx
# Copy or link the opscore_sdk directory into your project
```
*(Note: Proper packaging is TBD)*

## Usage

### Synchronous Client

```python
from opscore_sdk.client import OpsCoreClientSync
from opscore_sdk.exceptions import OpsCoreApiError, NotFoundError

# Replace with your Ops-Core API details
OPSCORE_BASE_URL = "http://localhost:8000" # Or your deployed URL
OPSCORE_API_KEY = "your-opscore-api-key" # Use the correct key
AGENT_ID = "your-agent-id" # The ID of the agent

client = OpsCoreClientSync(base_url=OPSCORE_BASE_URL, api_key=OPSCORE_API_KEY)

try:
    # Update agent state
    client.update_state(agent_id=AGENT_ID, state="active", details={"current_task": "processing data"})
    print(f"Agent {AGENT_ID} state updated.")

    # Get agent state
    current_state = client.get_state(agent_id=AGENT_ID)
    print(f"Current state for agent {AGENT_ID}: {current_state}")

    # Trigger a workflow
    workflow_response = client.trigger_workflow(
        agent_id=AGENT_ID,
        workflow_definition_id="sample-workflow-v1", # Replace with a valid workflow ID
        initial_payload={"input_data": "some value"}
    )
    print(f"Workflow triggered: Session ID = {workflow_response['sessionId']}")

except NotFoundError:
    print(f"Error: Agent {AGENT_ID} or workflow not found.")
except OpsCoreApiError as e:
    print(f"API Error: {e.status_code} - {e.detail}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    client.close() # Close the client connection

# Using context manager (recommended)
with OpsCoreClientSync(base_url=OPSCORE_BASE_URL, api_key=OPSCORE_API_KEY) as client:
    try:
        state = client.get_state(agent_id=AGENT_ID)
        print(f"State via context manager: {state}")
    except Exception as e:
        print(f"Error: {e}")

```

### Asynchronous Client

```python
import asyncio
from opscore_sdk.client import OpsCoreClientAsync
from opscore_sdk.exceptions import OpsCoreApiError, NotFoundError

# Replace with your Ops-Core API details
OPSCORE_BASE_URL = "http://localhost:8000" # Or your deployed URL
OPSCORE_API_KEY = "your-opscore-api-key" # Use the correct key
AGENT_ID = "your-agent-id" # The ID of the agent

async def main():
    client = OpsCoreClientAsync(base_url=OPSCORE_BASE_URL, api_key=OPSCORE_API_KEY)
    try:
        # Update agent state
        await client.update_state(agent_id=AGENT_ID, state="idle", details={"reason": "task complete"})
        print(f"Agent {AGENT_ID} state updated (async).")

        # Get agent state
        current_state = await client.get_state(agent_id=AGENT_ID)
        print(f"Current state for agent {AGENT_ID} (async): {current_state}")

        # Trigger a workflow
        workflow_response = await client.trigger_workflow(
            agent_id=AGENT_ID,
            workflow_definition_id="sample-workflow-v1", # Replace with a valid workflow ID
            initial_payload={"input_data": "async value"}
        )
        print(f"Workflow triggered (async): Session ID = {workflow_response['sessionId']}")

    except NotFoundError:
        print(f"Error: Agent {AGENT_ID} or workflow not found.")
    except OpsCoreApiError as e:
        print(f"API Error: {e.status_code} - {e.detail}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await client.close() # Close the client connection

    # Using async context manager (recommended)
    async with OpsCoreClientAsync(base_url=OPSCORE_BASE_URL, api_key=OPSCORE_API_KEY) as client:
        try:
            state = await client.get_state(agent_id=AGENT_ID)
            print(f"State via async context manager: {state}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())