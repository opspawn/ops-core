# tests/simulated_agent/main.py
import os
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
import httpx

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SimulatedAgent")

# --- Configuration ---
AGENTKIT_API_URL = os.getenv("AGENTKIT_API_URL", "http://localhost:8001/v1")
OPSCORE_API_URL = os.getenv("OPSCORE_API_URL", "http://localhost:8000/v1") # Ops-Core base URL
OPSCORE_API_KEY = os.getenv("OPSCORE_API_KEY", "test-api-key") # Key to auth WITH Ops-Core
# AGENT_ID = os.getenv("AGENT_ID", f"sim-agent-{uuid.uuid4()}") # Initial configured ID - will be replaced by AgentKit ID
AGENT_NAME = os.getenv("AGENT_NAME", "SimulatedAgent")
AGENT_VERSION = os.getenv("AGENT_VERSION", "0.1.0")
# The endpoint AgentKit should call on this agent
AGENT_CONTACT_ENDPOINT = os.getenv("AGENT_CONTACT_ENDPOINT", "http://simulated_agent:8080/task")
# The port this agent service listens on
AGENT_PORT = int(os.getenv("AGENT_PORT", "8080"))

# Global variable to store the actual agent ID assigned by AgentKit
ACTUAL_AGENT_ID = None

# --- AgentKit SDK (Simplified Inline Version) ---
# In a real scenario, this would import the actual agentkit.sdk
class AgentKitError(Exception):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class AgentKitClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        # Use a persistent client for connection pooling
        self._client = httpx.AsyncClient(timeout=10.0) # Added timeout

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"AgentKit API Error ({e.response.status_code}) for {method} {url}: {e.response.text}")
            raise AgentKitError(
                f"AgentKit API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                response_data=e.response.text # Return text for non-JSON errors
            ) from e
        except httpx.RequestError as e:
            logger.error(f"AgentKit Network Error for {method} {url}: {e}")
            raise AgentKitError(f"Network error connecting to AgentKit: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during AgentKit request to {method} {url}: {e}")
            raise AgentKitError(f"Unexpected error during AgentKit request: {e}") from e


    async def register_agent(self, agent_name: str, capabilities: list[str], version: str, contact_endpoint: str, metadata: dict | None = None) -> str:
        payload = {
            "agentName": agent_name,
            "capabilities": capabilities,
            "version": version,
            "contactEndpoint": contact_endpoint,
            "metadata": metadata or {},
        }
        logger.info(f"Registering agent '{agent_name}' with AgentKit at {self.base_url}...")
        response_data = await self._request("POST", "/agents/register", json=payload)
        agent_id = response_data.get("data", {}).get("agentId")
        if not agent_id:
             raise AgentKitError("Failed to get agentId from registration response", response_data=response_data)
        logger.info(f"Agent registered successfully with ID: {agent_id}")
        return agent_id

# --- Ops-Core SDK (Simplified Inline Version) ---
# In a real scenario, this would import the actual opscore_sdk
class OpsCoreError(Exception):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class OpsCoreClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0) # Added timeout

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json" # Ensure content type

        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            # Handle cases where response might be empty or not JSON
            if response.status_code == 204 or not response.content:
                 return None # Or return a standard success dict
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"OpsCore API Error ({e.response.status_code}) for {method} {url}: {e.response.text}")
            raise OpsCoreError(
                f"OpsCore API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                response_data=e.response.text
            ) from e
        except httpx.RequestError as e:
            logger.error(f"OpsCore Network Error for {method} {url}: {e}")
            raise OpsCoreError(f"Network error connecting to OpsCore: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during OpsCore request to {method} {url}: {e}")
            raise OpsCoreError(f"Unexpected error during OpsCore request: {e}") from e

    async def report_state(self, agent_id: str, state: str, details: dict | None = None):
        path = f"/opscore/agent/{agent_id}/state" # Correct path based on docs
        payload = {
            "state": state,
            "details": details or {},
            # OpsCore API expects agentId in payload based on its models,
            # even though it's in the URL path. Let's include it for safety.
            # Update: OpsCore state endpoint schema doesn't require agentId in body
            # "agentId": agent_id, # Removed based on OpsCore schema review
        }
        logger.info(f"Reporting state '{state}' for agent {agent_id} to OpsCore at {self.base_url}...")
        await self._request("POST", path, json=payload)
        logger.info(f"State '{state}' reported successfully for agent {agent_id}.")


# --- FastAPI App ---
# Shared clients for the lifespan of the application
clients = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize clients and register agent
    logger.info("Simulated Agent starting up...")
    clients["agentkit"] = AgentKitClient(base_url=AGENTKIT_API_URL)
    clients["opscore"] = OpsCoreClient(base_url=OPSCORE_API_URL, api_key=OPSCORE_API_KEY)

    registered = False
    attempts = 0
    max_attempts = 5
    global ACTUAL_AGENT_ID # Declare intent to modify the global variable
    while not registered and attempts < max_attempts:
        attempts += 1
        try:
            # Use a temporary ID hint for registration, but capture the actual ID returned
            temp_id_hint = f"sim-agent-{uuid.uuid4()}"
            ACTUAL_AGENT_ID = await clients["agentkit"].register_agent(
                agent_name=AGENT_NAME,
                capabilities=["simulation"],
                version=AGENT_VERSION,
                contact_endpoint=AGENT_CONTACT_ENDPOINT,
                metadata={"id_hint": temp_id_hint} # Pass a hint
            )
            # IMPORTANT: Use the ID returned by AgentKit
            registered = True
            logger.info(f"Simulated Agent '{AGENT_NAME}' registered successfully with ID '{ACTUAL_AGENT_ID}'")
        except AgentKitError as e:
            logger.error(f"Attempt {attempts}/{max_attempts}: Failed to register with AgentKit: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
             logger.error(f"Attempt {attempts}/{max_attempts}: Unexpected error during registration: {e}. Retrying in 5 seconds...")
             await asyncio.sleep(5)

    if not registered:
        logger.critical("Failed to register with AgentKit after multiple attempts. Shutting down.")
        # Optionally raise an exception to prevent FastAPI from starting fully
        raise RuntimeError("AgentKit registration failed.")

    yield # Application runs here

    # Shutdown: Close clients
    logger.info("Simulated Agent shutting down...")
    if "agentkit" in clients:
        await clients["agentkit"].close()
    if "opscore" in clients:
        await clients["opscore"].close()
    logger.info("Clients closed.")


app = FastAPI(lifespan=lifespan)

class TaskPayload(BaseModel):
    # Define expected structure of payload received from AgentKit
    task_name: str | None = None
    task_parameters: dict | None = Field(default_factory=dict)
    opscore_task_id: str | None = None # Optional context from Ops-Core

async def simulate_task_processing(task_id: str | None):
    """Simulates work and reports state changes."""
    opscore_client: OpsCoreClient = clients["opscore"]
    task_details = {"opscore_task_id": task_id} if task_id else {}
    try:
        logger.info(f"Task received (OpsCore Task ID: {task_id}). Simulating work...")
        # 1. Report 'active' state
        # Use the ACTUAL_AGENT_ID for reporting state
        await opscore_client.report_state(ACTUAL_AGENT_ID, "active", details=task_details)

        # 2. Simulate work
        await asyncio.sleep(2) # Simulate 2 seconds of work

        # 3. Report 'idle' state (or 'completed')
        logger.info(f"Task simulation complete (OpsCore Task ID: {task_id}). Reporting idle.")
        # Use the ACTUAL_AGENT_ID for reporting state
        await opscore_client.report_state(ACTUAL_AGENT_ID, "idle", details=task_details)

    except OpsCoreError as e:
        logger.error(f"Failed to report state to OpsCore for task {task_id}: {e}")
        # Optionally report an 'error' state back to OpsCore if state reporting fails critically
        try:
            await opscore_client.report_state(ACTUAL_AGENT_ID, "error", details={"error": str(e), **task_details})
        except Exception as report_err:
            logger.error(f"Failed even reporting error state back to OpsCore: {report_err}")
    except Exception as e:
        logger.error(f"Unexpected error during task simulation for task {task_id}: {e}")
        # Report error state if possible
        try:
            await opscore_client.report_state(ACTUAL_AGENT_ID, "error", details={"error": f"Unexpected simulation error: {str(e)}", **task_details})
        except Exception as report_err:
            logger.error(f"Failed reporting unexpected error state back to OpsCore: {report_err}")


@app.post("/task") # This path should match AGENT_CONTACT_ENDPOINT
async def receive_task(request: Request, background_tasks: BackgroundTasks):
    """Endpoint called by AgentKit to dispatch a task."""
    try:
        payload_data = await request.json()
        logger.info(f"Received task payload: {payload_data}")

        # Basic validation (can use Pydantic model if structure is known)
        task = TaskPayload.model_validate(payload_data.get("payload", {}))
        opscore_task_id = payload_data.get("opscore_task_id") # Extract context if provided

        # Start background task for simulation
        background_tasks.add_task(simulate_task_processing, opscore_task_id)

        # Acknowledge receipt to AgentKit immediately
        return {"status": "success", "message": "Task received and processing started."}

    except Exception as e:
        logger.error(f"Error processing incoming task request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid task payload: {e}")

@app.get("/health")
async def health_check():
    # Basic health check, return the actual agent ID assigned by AgentKit
    if ACTUAL_AGENT_ID is None:
        # Agent hasn't registered yet, return a temporary status or error
        return {"status": "registering", "agent_id": None}
    return {"status": "healthy", "agent_id": ACTUAL_AGENT_ID}

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Log the configured ID hint, but note it might change
    configured_id_hint = os.getenv("AGENT_ID", f"sim-agent-{uuid.uuid4()}")
    logger.info(f"Starting Simulated Agent '{AGENT_NAME}' (Configured ID Hint: {configured_id_hint}) on port {AGENT_PORT}")
    logger.info(f"AgentKit API URL: {AGENTKIT_API_URL}")
    logger.info(f"OpsCore API URL: {OPSCORE_API_URL}")
    logger.info(f"Contact Endpoint: {AGENT_CONTACT_ENDPOINT}")

    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)