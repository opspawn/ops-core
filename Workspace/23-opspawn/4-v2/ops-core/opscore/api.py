"""
Ops-Core API Layer (FastAPI)

Exposes endpoints for interacting with Ops-Core functionalities,
including agent state updates and workflow management.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from typing import Dict, Any, Annotated

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Placeholder imports - will be replaced with actual implementations
from . import models # Import models
from . import lifecycle, workflow, storage # Import lifecycle, workflow, storage modules
from .models import AgentStateUpdatePayload, StatusResponse, ErrorResponse, WorkflowTriggerRequest, WorkflowTriggerResponse, WorkflowDefinition
# from . import config, exceptions
from .logging_config import get_logger, setup_logging

# Setup logging as early as possible
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level=LOG_LEVEL)
logger = get_logger(__name__)

# TODO: Implement a proper config loading mechanism (e.g., Pydantic BaseSettings)
# For now, load directly from environment variables
EXPECTED_API_KEY = os.getenv("OPSCORE_API_KEY")
if not EXPECTED_API_KEY:
    logger.warning("OPSCORE_API_KEY environment variable not set. Using default 'test-api-key'. THIS IS INSECURE.")
    EXPECTED_API_KEY = "test-api-key" # Fallback for local dev if not set


app = FastAPI(
    title="Ops-Core API",
    description="API for managing AI agent lifecycles and workflows via Ops-Core.",
    version="0.1.0",
)

# --- Dependency for API Key Authentication ---
async def verify_api_key(authorization: Annotated[str | None, Header()] = None):
    """Dependency to verify the API key provided in the Authorization header."""
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not EXPECTED_API_KEY or token != EXPECTED_API_KEY:
        logger.warning(f"Invalid API key received. Scheme: {scheme}, Token provided: {'Yes' if token else 'No'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return token

# --- API Endpoints ---

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

# Use the model defined in models.py
# from .models import AgentStateUpdatePayload

@app.post(
    "/v1/opscore/agent/{agent_id}/state",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Agent Lifecycle"],
    dependencies=[Depends(verify_api_key)] # Enable API key check
)
async def update_agent_state(
    agent_id: str,
    state_update: models.AgentStateUpdatePayload, # Use the imported model
    # request: Request # Can be used to get headers, etc. if needed
):
    """
    Endpoint for agents (via SDK) to report their state updates.
    Requires API Key authentication.
    """
    logger.info(f"Received state update for agent {agent_id}: State='{state_update.state}' Timestamp='{state_update.timestamp}'")
    # Pydantic performs basic validation. Explicit check for path/payload ID match:
    if agent_id != state_update.agentId:
        logger.warning(f"Agent ID mismatch in state update: Path='{agent_id}', Payload='{state_update.agentId}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent ID in path does not match agent ID in payload",
        )

    try:
        # Call the actual lifecycle management function
        lifecycle.set_state(
            agent_id=agent_id,
            new_state=state_update.state,
            details=state_update.details,
            timestamp=state_update.timestamp # TODO: Consider parsing timestamp in lifecycle
        )
        logger.info(f"Successfully processed state update for agent {agent_id}")
        # Use the standard response model
        return models.StatusResponse(message="State update accepted")
    except Exception as e: # TODO: Replace with specific exceptions from lifecycle module
        logger.error(f"Error processing state update for agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error processing state update." # Avoid leaking exception details
        )

@app.post(
    "/v1/opscore/agent/{agent_id}/workflow",
    response_model=WorkflowTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Workflow Orchestration"],
    dependencies=[Depends(verify_api_key)] # Enable API key check
)
async def trigger_workflow(
    agent_id: str,
    trigger_request: WorkflowTriggerRequest
):
    """
    Endpoint to trigger a workflow for a specific agent.

    Requires API Key authentication. Accepts either a pre-defined
    `workflowDefinitionId` or an inline `workflowDefinition`.
    """
    logger.info(f"Workflow trigger request received for agent {agent_id}")

    # 1. Verify Agent Exists
    if not storage.agent_exists(agent_id):
        logger.error(f"Cannot trigger workflow: Agent {agent_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    # 2. Get or Create Workflow Definition
    workflow_def = None
    workflow_id = None
    try:
        if trigger_request.workflowDefinitionId:
            workflow_id = trigger_request.workflowDefinitionId
            logger.debug(f"Attempting to use existing workflow definition ID: {workflow_id}")
            # Retrieve definition from storage (assuming it returns the model or dict)
            workflow_def_data = storage.read_workflow_definition(workflow_id)
            if not workflow_def_data:
                 logger.error(f"Workflow definition not found for ID: {workflow_id}")
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition not found: {workflow_id}")
            # Assuming storage returns the model directly now
            workflow_def = workflow_def_data

        elif trigger_request.workflowDefinition:
            logger.debug("Using inline workflow definition from request.")
            # Validate and potentially store the inline definition
            # For now, just use it directly. Storing might require workflow.create_workflow
            workflow_def = trigger_request.workflowDefinition
            workflow_id = workflow_def.id # Get ID from the inline definition
            # Optional: Save the inline definition if it doesn't exist?
            if not storage.read_workflow_definition(workflow_id):
                 logger.info(f"Saving new inline workflow definition: {workflow_id}")
                 storage.save_workflow_definition(workflow_def) # Save the model

        else:
            # This case should be prevented by the Pydantic validator, but handle defensively
            logger.error("Workflow trigger request missing both definition ID and inline definition.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing workflowDefinitionId or workflowDefinition")

        if not workflow_def or not workflow_id:
             # Should not happen if logic above is correct
             raise ValueError("Failed to resolve workflow definition or ID.")

    except HTTPException:
        raise # Re-raise HTTP exceptions directly
    except Exception as e:
        logger.error(f"Error processing workflow definition for agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing workflow definition")

    # 3. Start Workflow Session
    try:
        session = lifecycle.start_session(agent_id=agent_id, workflow_id=workflow_id)
        logger.info(f"Started session {session.sessionId} for workflow {workflow_id} on agent {agent_id}")
    except ValueError as e: # Catch agent not found or duplicate session from lifecycle
         logger.error(f"Failed to start session for workflow {workflow_id} on agent {agent_id}: {e}", exc_info=True)
         # Distinguish between agent not found (already checked) and other errors
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to start session: {e}")
    except Exception as e:
        logger.error(f"Failed to start session for workflow {workflow_id} on agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start workflow session")

    # 4. Enqueue the First Task
    try:
        if not workflow_def.tasks:
            logger.warning(f"Workflow definition {workflow_id} has no tasks.")
            # Update session status?
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="completed", result={"message": "Workflow has no tasks"}))
            return WorkflowTriggerResponse(sessionId=session.sessionId, workflowId=workflow_id, message="Workflow triggered but has no tasks.")

        first_task_def = workflow_def.tasks[0] # Assuming first task is the entry point
        task_id = f"task_{uuid.uuid4()}" # Generate unique ID for the task instance

        # Prepare task data using the Task model structure
        task_payload = trigger_request.initialPayload or first_task_def.get("parameters", {}) # Use initial payload or default params

        task_instance_data = {
            "taskId": task_id,
            "workflowId": workflow_id,
            "sessionId": session.sessionId,
            "agentId": agent_id, # Initially assign to the triggering agent
            "taskDefinitionId": first_task_def.get("taskId"), # Link to the definition task ID
            "payload": task_payload,
            "status": "pending",
            # retryCount, maxRetries will use defaults from Task model or be overridden later
        }

        workflow.enqueue_task(task_instance_data)
        logger.info(f"Enqueued first task {task_id} for session {session.sessionId}")

    except Exception as e:
        logger.error(f"Failed to enqueue first task for session {session.sessionId}: {e}", exc_info=True)
        # Attempt to mark session as failed
        try:
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="failed", error=f"Failed to enqueue first task: {e}"))
        except Exception as update_err:
             logger.error(f"Additionally failed to update session {session.sessionId} status after enqueue error: {update_err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enqueue first task")

    # 5. Return Success Response
    return WorkflowTriggerResponse(sessionId=session.sessionId, workflowId=workflow_id)


# --- Add other endpoints as needed ---

# Example of how to run directly (for simple testing, use uvicorn command for production/dev)
if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this might bypass some configurations (like .env loading)
    # Prefer using `uvicorn opscore.api:app --reload`
    uvicorn.run(app, host="0.0.0.0", port=8000)
