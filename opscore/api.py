"""
Ops-Core API Layer (FastAPI)

Exposes endpoints for interacting with Ops-Core functionalities,
including agent state updates and workflow management.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from typing import Dict, Any, Annotated
import uuid # Import uuid module

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Placeholder imports - will be replaced with actual implementations
from . import models # Import models
from . import lifecycle, workflow, storage # Import lifecycle, workflow, storage modules
from .models import AgentStateUpdatePayload, StatusResponse, ErrorResponse, WorkflowTriggerRequest, WorkflowTriggerResponse, WorkflowDefinition, AgentNotificationPayload, AgentState # Added AgentState
from . import exceptions # Import custom exceptions
from .logging_config import get_logger, setup_logging
# Import the new middleware
from .middleware import ErrorHandlerMiddleware, RequestLoggingMiddleware

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

# --- Add Middleware ---
# Error handler should be outermost to catch all subsequent errors
app.add_middleware(ErrorHandlerMiddleware)
# Request logging follows
app.add_middleware(RequestLoggingMiddleware)


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
    # Logging is now handled by middleware
    # logger.info("Health check endpoint called.")
    return {"status": "ok"}


@app.post(
    "/v1/opscore/internal/agent/notify",
    status_code=status.HTTP_200_OK,
    tags=["Internal", "Agent Lifecycle"],
    response_model=StatusResponse,
    # Note: No API key dependency for now, assuming internal network call.
)
async def agent_notification(payload: AgentNotificationPayload):
    """
    Internal endpoint for AgentKit to notify Ops-Core about agent events
    (e.g., registration, deregistration).
    """
    # Logging handled by middleware
    # logger.info(f"Received agent notification: Event='{payload.event_type}', AgentName='{payload.agent_details.agentName}'")

    # Removed broad try/except block; middleware handles OpsCoreError and Exception
    if payload.event_type.upper() == "REGISTER":
        agent_id = payload.agent_details.agentId
        if not agent_id:
            logger.error("Received REGISTER notification with missing agentId in details.")
            # Raise HTTPException directly for validation errors
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing agentId in agent_details for REGISTER event.")

        logger.info(f"Registering agent '{payload.agent_details.agentName}' with ID from notification: {agent_id}")
        try:
            lifecycle.register_agent(
                agent_id=agent_id,
                details=payload.agent_details
            )
            logger.info(f"Successfully registered agent {agent_id} via notification.")
            return StatusResponse(message=f"Agent {agent_id} registered successfully.")
        except exceptions.AgentAlreadyExistsError as e:
            # Specific handling for already exists - maybe return success but log?
            logger.warning(f"Attempted to register an agent that might already exist: {e}")
            return StatusResponse(message=f"Agent potentially already registered: {e}")
        # Other OpsCoreErrors (InvalidStateError, StorageError) will be caught by middleware

    elif payload.event_type.upper() == "DEREGISTER":
        # TODO: Implement deregistration logic in lifecycle module
        logger.warning(f"Received DEREGISTER notification for agent '{payload.agent_details.agentName}', but deregistration logic is not yet implemented.")
        return StatusResponse(message="DEREGISTER notification received but not fully processed.")
    else:
        logger.warning(f"Received unknown agent notification event type: {payload.event_type}")
        # Raise HTTPException directly for validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event type: {payload.event_type}"
        )


@app.post(
    "/v1/opscore/agent/{agent_id}/state",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Agent Lifecycle"],
    dependencies=[Depends(verify_api_key)] # Enable API key check
)
async def update_agent_state(
    agent_id: str,
    state_update: models.AgentStateUpdatePayload,
):
    """
    Endpoint for agents (via SDK) to report their state updates.
    Requires API Key authentication.
    """
    # Logging handled by middleware
    # logger.info(f"Received state update for agent {agent_id}: State='{state_update.state}' Timestamp='{state_update.timestamp}'")

    # Pydantic performs basic validation. Explicit check for path/payload ID match:
    if agent_id != state_update.agentId:
        logger.warning(f"Agent ID mismatch in state update: Path='{agent_id}', Payload='{state_update.agentId}'")
        # Raise HTTPException directly for validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent ID in path does not match agent ID in payload",
        )

    # Removed broad try/except block; middleware handles OpsCoreError and Exception
    # Specific OpsCoreErrors (AgentNotFound, InvalidState, StorageError) will be caught by middleware
    lifecycle.set_state(
        agent_id=agent_id,
        new_state=state_update.state,
        details=state_update.details,
        timestamp=state_update.timestamp
    )
    logger.info(f"Successfully processed state update for agent {agent_id}")
    return models.StatusResponse(message="State update accepted")


@app.get(
   "/v1/opscore/agent/{agent_id}/state",
   response_model=models.AgentState,
   tags=["Agent Lifecycle"],
   dependencies=[Depends(verify_api_key)] # Enable API key check
)
async def get_agent_state(agent_id: str):
   """
   Retrieves the current state of a specific agent.
   Requires API Key authentication.
   """
   # Logging handled by middleware
   # logger.info(f"Received request for current state of agent {agent_id}")

   # Removed broad try/except block; middleware handles OpsCoreError and Exception
   # Specific OpsCoreErrors (AgentNotFound, StorageError) will be caught by middleware
   agent_state = lifecycle.get_state(agent_id=agent_id)
   # The AgentNotFoundError should be raised by get_state if not found,
   # and caught by the middleware. This check might be redundant if get_state guarantees raising.
   # Let's assume get_state raises AgentNotFoundError as expected.
   # However, lifecycle.get_state returns None if no state history exists, even if the agent is registered.
   # We should handle the None case explicitly here.
   if not agent_state:
        logger.warning(f"No state found for agent {agent_id} during GET state request (lifecycle.get_state returned None). Returning 404.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No state found for agent {agent_id}")

   logger.debug(f"Returning state for agent {agent_id}: {agent_state.state}")
   return agent_state


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
    # Logging handled by middleware
    # logger.info(f"Workflow trigger request received for agent {agent_id}")

    # 1. Resolve Workflow Definition
    workflow_def = None
    workflow_id = None
    try:
        if trigger_request.workflowDefinitionId:
            workflow_id = trigger_request.workflowDefinitionId
            logger.debug(f"Attempting to use existing workflow definition ID: {workflow_id}")
            workflow_def = storage.read_workflow_definition(workflow_id) # Raises NotFoundError if missing
            if not workflow_def: # Should be caught by the exception below, but defensive check
                 raise exceptions.WorkflowDefinitionNotFoundError(workflow_id)

        elif trigger_request.workflowDefinition:
            logger.debug("Using inline workflow definition from request.")
            workflow_def_data = trigger_request.workflowDefinition # Get the raw data (likely dict)

            # Validate and convert to model instance
            try:
                if isinstance(workflow_def_data, models.WorkflowDefinition):
                     # Already a model instance (less likely path but handle defensively)
                     workflow_def = workflow_def_data
                elif isinstance(workflow_def_data, dict):
                     workflow_def = models.WorkflowDefinition(**workflow_def_data)
                else:
                     # Should be caught by FastAPI/Pydantic earlier, but raise if not
                     raise ValueError("workflowDefinition must be a valid dictionary or WorkflowDefinition object.")
                workflow_id = workflow_def.id # Now safe to access attribute
            except Exception as validation_error: # Catch Pydantic validation errors etc.
                logger.error(f"Invalid inline workflow definition provided: {validation_error}", exc_info=True)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid inline workflowDefinition: {validation_error}")

            # Optional: Save the inline definition if it doesn't exist?
            existing_def = storage.read_workflow_definition(workflow_id)
            if not existing_def:
                 logger.info(f"Saving new inline workflow definition: {workflow_id}")
                 storage.save_workflow_definition(workflow_def) # Save the model

        else:
            # Pydantic should prevent this, but raise validation error if it occurs
            logger.error("Workflow trigger request missing both definition ID and inline definition.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing workflowDefinitionId or workflowDefinition")

        if not workflow_def or not workflow_id:
             # Should not happen if logic above is correct
             logger.error("Internal error: Failed to resolve workflow definition or ID.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error resolving workflow definition.")

    except exceptions.WorkflowDefinitionNotFoundError as e:
        logger.warning(f"Workflow definition not found: {e}")
        # Raise HTTPException directly for specific not found errors
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # Other OpsCoreErrors (StorageError, InvalidStateError) and generic Exceptions
    # during definition resolution will be caught by middleware.

    # 2. Start Workflow Session
    # Agent existence checked here. AgentNotFoundError, StorageError, other OpsCoreError
    # caught by middleware.
    session = lifecycle.start_session(agent_id=agent_id, workflow_id=workflow_id)
    logger.info(f"Started session {session.sessionId} for workflow {workflow_id} on agent {agent_id}")

    # 3. Enqueue the First Task
    try:
        if not workflow_def.tasks:
            logger.warning(f"Workflow definition {workflow_id} has no tasks.")
            # Update session status?
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="completed", result={"message": "Workflow has no tasks"}))
            return WorkflowTriggerResponse(sessionId=session.sessionId, workflowId=workflow_id, message="Workflow triggered but has no tasks.")

        first_task_def = workflow_def.tasks[0]
        task_id = f"task_{uuid.uuid4()}"
        task_payload = trigger_request.initialPayload or first_task_def.get("parameters", {})

        task_instance_data = {
            "taskId": task_id,
            "workflowId": workflow_id,
            "sessionId": session.sessionId,
            "agentId": agent_id,
            "taskDefinitionId": first_task_def.get("taskId"),
            "payload": task_payload,
            "status": "pending",
        }

        # Enqueue task. InvalidStateError or other OpsCoreErrors caught by middleware.
        workflow.enqueue_task(task_instance_data)
        logger.info(f"Enqueued first task {task_id} for session {session.sessionId}")

    except Exception as e: # Catch potential errors during enqueue *after* session started
        error_msg = f"Failed to enqueue first task after starting session {session.sessionId}: {e}"
        logger.error(error_msg, exc_info=True)
        # Attempt to mark session as failed since enqueue failed
        try:
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="failed", error=str(e)))
        except Exception as update_err:
             logger.error(f"Additionally failed to update session {session.sessionId} status after enqueue error: {update_err}")
        # Re-raise the original exception to be handled by middleware
        raise e

    # 4. Return Success Response
    return WorkflowTriggerResponse(sessionId=session.sessionId, workflowId=workflow_id)


# --- Add other endpoints as needed ---

# Example of how to run directly (for simple testing, use uvicorn command for production/dev)
if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this might bypass some configurations (like .env loading)
    # Prefer using `uvicorn opscore.api:app --reload`
    uvicorn.run(app, host="0.0.0.0", port=8000)
