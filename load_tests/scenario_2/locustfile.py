import random
import time
import os
import json
from locust import HttpUser, task, between, constant
from datetime import datetime, timezone

# Get Ops-Core API Key from environment variable
OPSCORE_API_KEY = os.environ.get("OPSCORE_API_KEY", "dummy_api_key")

# Sample workflow definition from docs/sample_workflow.json
SAMPLE_WORKFLOW_DEFINITION = {
  "id": "sample_workflow_id",
  "name": "Sample Load Test Workflow",
  "description": "A simple workflow for performance testing.",
  "version": "1.0",
  "tasks": [
    {
      "taskId": "step_1",
      "name": "First Step",
      "agentCapability": "test_capability",
      "parameters": {
        "message": "This is the first step."
      },
      "nextTaskId": "step_2"
    },
    {
      "taskId": "step_2",
      "name": "Second Step",
      "agentCapability": "another_capability",
      "parameters": {
        "value": 123
      },
      "nextTaskId": None
    }
  ]
}

class WorkflowUser(HttpUser):
    """
    Locust user class for Scenario 2: Workflow Initiation Load.
    Focuses on the POST /workflow endpoint.
    """
    # Wait time as defined in Scenario 2 plan (30 to 60 seconds between tasks)
    wait_time = between(30, 60)

    # Set the host from environment variable or default
    host = os.environ.get("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        """
        Called when a Locust user starts.
        Set the default headers for API Key authentication and register the agent.
        """
        self.client.headers = {"Authorization": f"Bearer {OPSCORE_API_KEY}"}
        # Generate a unique agent ID for each user instance
        self.agent_id = f"workflow-agent-{random.randint(10000, 99999)}"
        print(f"Locust workflow user starting with agent ID: {self.agent_id}")
        # Note: Agent registration is assumed to be handled by a separate process
        # or is not strictly required for this specific workflow initiation test,
        # as the workflow endpoint might not immediately require agent state.
        # If registration is needed, add a call here similar to Scenario 1's on_start.

    @task(1) # Task weight of 1
    def trigger_workflow(self):
        """
        Simulates triggering a workflow for the agent.
        """
        workflow_payload = {
            "agentId": self.agent_id,
            "workflowDefinition": SAMPLE_WORKFLOW_DEFINITION,
            "context": {"load_test": True, "user": f"user-{self.agent_id}", "scenario": 2}
        }
        # Use catch_response=True to manually mark success/failure if needed
        self.client.post(f"/v1/opscore/agent/{self.agent_id}/workflow", json=workflow_payload, name="/v1/opscore/agent/[id]/workflow")