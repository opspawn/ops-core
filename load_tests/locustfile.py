import time
import uuid
from locust import HttpUser, task, between

class OpsCoreUser(HttpUser):
    """
    Locust user class that simulates calls to the Ops-Core API.
    """
    # Wait time between tasks for a user (e.g., 0.5 to 2 seconds)
    wait_time = between(0.5, 2.0)
    host = "http://127.0.0.1:8000" # Default host if not specified on CLI

    @task
    def submit_agent_task(self):
        """
        Simulates submitting an 'agent_run' task via the REST API.
        """
        headers = {"Content-Type": "application/json"}

        # Construct the JSON payload directly according to TaskCreateRequest schema
        payload = {
            "task_type": "agent_run",
            "input_data": {
                 "goal": "Simulate agent execution under load.",
                 # Add any other necessary input data for agent_run tasks
                 # e.g., "agent_config": {...}, "tool_specs": [...]
                 "inject_mcp_proxy": False # Assuming no MCP needed for basic load test
            }
        }

        with self.client.post(
            "/api/v1/tasks/",
            json=payload, # Send the corrected payload
            headers=headers,
            name="/api/v1/tasks/ (POST agent_run)", # Name for Locust stats
            catch_response=True # Allows checking the response
        ) as response:
            if response.status_code == 201:
                try:
                    # Verify the response structure (optional but good practice)
                    response_data = response.json()
                    if "task_id" in response_data and "status" in response_data:
                        response.success()
                    else:
                        response.failure(f"Unexpected response format: {response.text}")
                except ValueError:
                    response.failure(f"Failed to decode JSON response: {response.text}")
            else:
                response.failure(
                    f"Failed to create task. Status: {response.status_code}, Body: {response.text}"
                )

    # Add other tasks here if needed, e.g., GET /api/v1/tasks/{id}
    # @task
    # def get_task_status(self):
    #     # Requires storing task IDs created by submit_agent_task
    #     pass
