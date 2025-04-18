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
    return {"status": "ok"} # Corrected indentation (4 spaces)


@app.post( # Corrected indentation (0 spaces)
    "/v1/opscore/internal/agent/notify",
    status_code=status.HTTP_200_OK,
    tags=["Internal", "Agent Lifecycle"],
    response_model=StatusResponse,
    # Note: No API key dependency for now, assuming internal network call.
    # Add security later if needed (e.g., separate internal key, network policies).
)
async def agent_notification(payload: AgentNotificationPayload): # Corrected indentation (0 spaces)
    """ # Corrected indentation (4 spaces)
    Internal endpoint for AgentKit to notify Ops-Core about agent events
    (e.g., registration, deregistration).
    """
    logger.info(f"Received agent notification: Event='{payload.event_type}', AgentName='{payload.agent_details.agentName}'") # Corrected indentation (4 spaces)

    try: # Corrected indentation (4 spaces)
        if payload.event_type.upper() == "REGISTER": # Corrected indentation (8 spaces)
           # Use the agent ID provided by AgentKit in the notification
           agent_id = payload.agent_details.agentId # Corrected indentation (12 spaces)
           if not agent_id:
                logger.error("Received REGISTER notification with missing agentId in details.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing agentId in agent_details for REGISTER event.")

           logger.info(f"Registering agent '{payload.agent_details.agentName}' with ID from notification: {agent_id}") # Corrected indentation (12 spaces)
           lifecycle.register_agent( # Corrected indentation (12 spaces)
               agent_id=agent_id, # Use ID from payload
               details=payload.agent_details # Pass the nested details model
           )
            logger.info(f"Successfully registered agent {agent_id} via notification.") # Corrected indentation (12 spaces)
            return StatusResponse(message=f"Agent {agent_id} registered successfully.") # Corrected indentation (12 spaces)

        elif payload.event_type.upper() == "DEREGISTER": # Corrected indentation (8 spaces)
            # TODO: Implement deregistration logic in lifecycle module
            # agent_id = find_agent_id_by_details(payload.agent_details) # Need a way to find the agent
            # if agent_id:
            #     lifecycle.deregister_agent(agent_id)
            logger.warning(f"Received DEREGISTER notification for agent '{payload.agent_details.agentName}', but deregistration logic is not yet implemented.") # Corrected indentation (12 spaces)
            return StatusResponse(message="DEREGISTER notification received but not fully processed.") # Corrected indentation (12 spaces)
        else: # Corrected indentation (8 spaces)
            logger.warning(f"Received unknown agent notification event type: {payload.event_type}") # Corrected indentation (12 spaces)
            raise HTTPException( # Corrected indentation (12 spaces)
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown event type: {payload.event_type}"
            )
    except exceptions.AgentAlreadyExistsError as e: # Indentation (4 spaces)
        # This might happen if AgentKit sends multiple REGISTER events for the same agent details
        # Or if our lookup finds an existing agent based on details before generating ID (if we change logic)
        logger.warning(f"Attempted to register an agent that might already exist: {e}") # Corrected indentation (8 spaces)
        # Decide on behavior: ignore, update, or error? For now, let's return success but log warning.
        # Consider adding agent lookup by details if needed.
        return StatusResponse(message=f"Agent potentially already registered: {e}") # Corrected indentation (8 spaces)
    except exceptions.InvalidStateError as e: # Catch validation errors from lifecycle/storage # Indentation (4 spaces)
        logger.error(f"Invalid data during agent notification processing: {e}", exc_info=True) # Corrected indentation (8 spaces)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) # Corrected indentation (8 spaces)
    except exceptions.StorageError as e: # Corrected indentation (4 spaces)
       logger.error(f"Storage error processing agent notification: {e}", exc_info=True) # Corrected indentation (8 spaces)
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage error processing agent notification.") # Corrected indentation (8 spaces)
    except Exception as e: # Corrected indentation (4 spaces)
        logger.error(f"Unexpected error processing agent notification: {e}", exc_info=True) # Corrected indentation (8 spaces)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error processing agent notification.") # Corrected indentation (8 spaces)

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
        # Call the actual lifecycle management function (Corrected indentation: 8 spaces)
        lifecycle.set_state( # Corrected indentation: 8 spaces
            agent_id=agent_id, # Corrected indentation: 12 spaces
            new_state=state_update.state, # Corrected indentation: 12 spaces
            details=state_update.details, # Corrected indentation: 12 spaces
            timestamp=state_update.timestamp # TODO: Consider parsing timestamp in lifecycle (Corrected indentation: 12 spaces)
        ) # Corrected indentation: 8 spaces
        logger.info(f"Successfully processed state update for agent {agent_id}") # Indentation: 8 spaces (already correct)
        # Use the standard response model
        return models.StatusResponse(message="State update accepted")
    except exceptions.AgentNotFoundError as e:
        logger.warning(f"Agent not found during state update: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except exceptions.InvalidStateError as e:
        logger.warning(f"Invalid state data during state update for agent {agent_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except exceptions.StorageError as e:
        logger.error(f"Storage error processing state update for agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage error processing state update.")
    except Exception as e:
        logger.error(f"Unexpected error processing state update for agent {agent_id}: {e}", exc_info=True)
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error processing state update.")


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
   logger.info(f"Received request for current state of agent {agent_id}")
   try:
       agent_state = lifecycle.get_state(agent_id=agent_id)
       if not agent_state: # get_state might return None if not found, though it should raise AgentNotFoundError
            logger.warning(f"Agent {agent_id} not found during GET state request (lifecycle.get_state returned None).")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found.")
       logger.debug(f"Returning state for agent {agent_id}: {agent_state.state}")
       return agent_state
   except exceptions.AgentNotFoundError as e:
       logger.warning(f"Agent {agent_id} not found during GET state request: {e}")
       raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
   except exceptions.StorageError as e:
       logger.error(f"Storage error retrieving state for agent {agent_id}: {e}", exc_info=True)
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage error retrieving agent state.")
   except Exception as e:
       logger.error(f"Unexpected error retrieving state for agent {agent_id}: {e}", exc_info=True)
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error retrieving agent state.")

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

    # Agent existence will be checked implicitly when starting the session later.

    # 2. Get or Create Workflow Definition
    workflow_def = None
    workflow_id = None
    try:
        if trigger_request.workflowDefinitionId:
            workflow_id = trigger_request.workflowDefinitionId
            logger.debug(f"Attempting to use existing workflow definition ID: {workflow_id}")
            # Retrieve definition from storage
            workflow_def_data = storage.read_workflow_definition(workflow_id) # Returns model or None
            if not workflow_def_data:
                 logger.error(f"Workflow definition not found for ID: {workflow_id}")
                 # Raise our custom exception, let the handler below catch it
                 raise exceptions.WorkflowDefinitionNotFoundError(workflow_id)
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
            # Raise a more specific error if needed, but Pydantic validation should catch this first.
            # For consistency, let's use InvalidStateError or a new dedicated one like InvalidRequestError if created.
            raise exceptions.InvalidStateError("Missing workflowDefinitionId or workflowDefinition")

        if not workflow_def or not workflow_id:
             # Should not happen if logic above is correct
             raise ValueError("Failed to resolve workflow definition or ID.")

    except HTTPException:
        raise # Re-raise HTTP exceptions directly
    except exceptions.WorkflowDefinitionNotFoundError as e:
        logger.warning(f"Workflow definition not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except exceptions.StorageError as e:
        logger.error(f"Storage error processing workflow definition for agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage error processing workflow definition.")
    except exceptions.InvalidStateError as e: # Catch potential error from the defensive check above
         logger.error(f"Invalid workflow trigger request for agent {agent_id}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing workflow definition for agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing workflow definition.")

    # 3. Start Workflow Session
    try:
        session = lifecycle.start_session(agent_id=agent_id, workflow_id=workflow_id)
        logger.info(f"Started session {session.sessionId} for workflow {workflow_id} on agent {agent_id}")
    except exceptions.AgentNotFoundError as e:
         logger.error(f"Failed to start session: Agent {agent_id} not found. Detail: {e}", exc_info=False) # Log less verbosely
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except exceptions.StorageError as e: # Catch storage errors during session creation
         logger.error(f"Storage error starting session for workflow {workflow_id} on agent {agent_id}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start session due to storage issue.")
    except exceptions.OpsCoreError as e: # Catch other specific OpsCore errors
        logger.error(f"OpsCore error starting session for workflow {workflow_id} on agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start workflow session: {e}")
    except Exception as e: # Catch unexpected errors
        logger.error(f"Unexpected error starting session for workflow {workflow_id} on agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error starting workflow session")

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

    except exceptions.InvalidStateError as e: # Catch validation errors from enqueue_task
        error_msg = f"Failed to enqueue first task due to invalid data: {e}"
        logger.error(f"{error_msg} for session {session.sessionId}", exc_info=True)
        # Attempt to mark session as failed
        try:
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="failed", error=error_msg))
        except Exception as update_err:
             logger.error(f"Additionally failed to update session {session.sessionId} status after enqueue error: {update_err}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e: # Catch other potential errors during enqueue
        error_msg = f"Failed to enqueue first task: {e}"
        logger.error(f"{error_msg} for session {session.sessionId}", exc_info=True)
        # Attempt to mark session as failed
        try:
            lifecycle.update_session(session.sessionId, models.SessionUpdate(status="failed", error=error_msg))
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
