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
from . import lifecycle # Import lifecycle module
# from . import workflow, config, exceptions, storage
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

# Placeholder for Workflow Trigger Endpoint
# @app.post("/v1/opscore/agent/{agent_id}/workflow", tags=["Workflow Orchestration"])
# async def trigger_workflow(agent_id: str, workflow_data: Dict[str, Any], auth: str = Depends(verify_api_key)):
#     """Endpoint to trigger a workflow for a specific agent."""
#     # TODO: Implement workflow triggering logic using models
#     logger.info(f"Workflow trigger request received for agent {agent_id}")
#     # workflow.start_workflow(agent_id=agent_id, workflow_config=workflow_data)
#     return models.StatusResponse(message="Workflow trigger accepted")


# --- Add other endpoints as needed ---

# Example of how to run directly (for simple testing, use uvicorn command for production/dev)
if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this might bypass some configurations (like .env loading)
    # Prefer using `uvicorn opscore.api:app --reload`
    uvicorn.run(app, host="0.0.0.0", port=8000)
