from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import httpx # For making async requests
import os
import logging # Added for logging webhook attempts/failures
import asyncio # Added for simulating work delay
from datetime import datetime, timezone # Added for timestamping state updates

# Basic logging setup for the mock service
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Ops-Core internal webhook URL (adjust if Ops-Core runs on a different port/service name)
OPSCORE_WEBHOOK_URL = os.getenv("OPSCORE_INTERNAL_URL", "http://opscore_service:8000") + "/v1/opscore/internal/agent/notify"
logger.info(f"Mock AgentKit configured to notify Ops-Core at: {OPSCORE_WEBHOOK_URL}")

# Ops-Core state update URL
OPSCORE_STATE_UPDATE_URL_TEMPLATE = os.getenv("OPSCORE_API_URL", "http://opscore_service:8000") + "/v1/opscore/agent/{agent_id}/state"
# API Key expected by Ops-Core (should match the one Ops-Core uses)
OPSCORE_API_KEY = os.getenv("OPSCORE_API_KEY", "test-api-key")

class AgentInfo(BaseModel):
    agentId: str # Corrected indentation (4 spaces)
    agentName: str # Corrected indentation (4 spaces)
    version: str # Corrected indentation (4 spaces)
    capabilities: List[str] # Corrected indentation (4 spaces)
    contactEndpoint: str # Corrected indentation (4 spaces)
    registrationTime: str # Corrected indentation (4 spaces)
    metadata: Dict[str, Any] # Corrected indentation (4 spaces)

agents: List[AgentInfo] = []

@app.post("/v1/agents")
async def register_agent(agent_info: AgentInfo):
   global agents
   # Check if agent already exists (simple check by ID)
   if any(agent.agentId == agent_info.agentId for agent in agents):
        logger.warning(f"Agent {agent_info.agentId} already registered.")
        # Optionally raise HTTPException or just return success
        # raise HTTPException(status_code=409, detail="Agent already registered")
        # For now, let's allow re-registration but skip webhook if already exists?
        # Or just proceed and let Ops-Core handle potential duplicates if needed.
        # Let's proceed for now.
        pass # Allow re-registration for simplicity in mock

   agents.append(agent_info)
   logger.info(f"Agent {agent_info.agentId} registered locally in mock AgentKit.")

   # --- Send Webhook Notification to Ops-Core ---
   # Map AgentInfo to the AgentRegistrationDetails structure expected by Ops-Core
   # Include agentId now, exclude registrationTime as Ops-Core generates its own
   agent_details_payload = {
       "agentId": agent_info.agentId, # Added agentId
       "agentName": agent_info.agentName,
       "version": agent_info.version,
       "capabilities": agent_info.capabilities,
       "contactEndpoint": agent_info.contactEndpoint,
       "metadata": agent_info.metadata,
   }
   notification_payload = {
       "event_type": "REGISTER",
       "agent_details": agent_details_payload
   }

   try:
       async with httpx.AsyncClient() as client:
           response = await client.post(OPSCORE_WEBHOOK_URL, json=notification_payload)
           response.raise_for_status() # Raise exception for 4xx/5xx responses
           logger.info(f"Successfully notified Ops-Core about agent {agent_info.agentId} registration. Status: {response.status_code}")
   except httpx.RequestError as exc:
       logger.error(f"Webhook Error: Failed to connect to Ops-Core at {OPSCORE_WEBHOOK_URL}. Error: {exc}")
       # Don't fail the agent registration in the mock, just log the webhook failure
   except httpx.HTTPStatusError as exc:
       logger.error(f"Webhook Error: Ops-Core returned an error status {exc.response.status_code} for agent {agent_info.agentId}. Response: {exc.response.text}")
       # Don't fail the agent registration in the mock
   except Exception as e:
       logger.error(f"Webhook Error: An unexpected error occurred while notifying Ops-Core: {e}", exc_info=True)
       # Don't fail the agent registration in the mock

   return {"status": "success", "message": f"Agent {agent_info.agentId} registered (webhook notification attempted)"}

@app.get("/v1/agents")
async def list_agents():
    return {"status": "success", "message": "Agents retrieved successfully.", "data": agents}

@app.post("/v1/agents/{agentId}/run")
async def run_agent(agentId: str, payload: Dict[str, Any]):
   """Simulates receiving a task and sending state updates back to Ops-Core."""
   logger.info(f"Received task for agent {agentId}: {payload}")

   # Helper function to send state updates
   async def update_opscore_state(target_agent_id: str, new_state: str, details: dict = None):
       state_update_url = OPSCORE_STATE_UPDATE_URL_TEMPLATE.format(agent_id=target_agent_id)
       headers = {"Authorization": f"Bearer {OPSCORE_API_KEY}"}
       state_payload = {
           "agentId": target_agent_id,
           "timestamp": datetime.now(timezone.utc).isoformat(),
           "state": new_state,
           "details": details or {}
       }
       try:
           async with httpx.AsyncClient() as client:
               response = await client.post(state_update_url, headers=headers, json=state_payload)
               response.raise_for_status()
               logger.info(f"Successfully sent state update '{new_state}' for agent {target_agent_id} to Ops-Core. Status: {response.status_code}")
       except httpx.RequestError as exc:
           logger.error(f"State Update Error: Failed to connect to Ops-Core at {state_update_url}. Error: {exc}")
       except httpx.HTTPStatusError as exc:
           logger.error(f"State Update Error: Ops-Core returned status {exc.response.status_code} for state '{new_state}' on agent {target_agent_id}. Response: {exc.response.text}")
       except Exception as e:
           logger.error(f"State Update Error: An unexpected error occurred: {e}", exc_info=True)

   # --- Simulate Task Execution and State Updates ---
   # 1. Set state to BUSY
   await update_opscore_state(agentId, "BUSY", {"current_task": payload.get("taskId", "unknown")})

   # 2. Simulate work (optional delay)
   await asyncio.sleep(0.1) # Simulate a short task duration

   # 3. Set state back to IDLE (or COMPLETED)
   # Let's use IDLE for simplicity in this mock
   await update_opscore_state(agentId, "IDLE", {"last_task_result": "simulated_success"})

   # Return success to the caller (Ops-Core workflow dispatcher)
   return {"status": "success", "message": f"Task received by agent {agentId} (state updates attempted)"}