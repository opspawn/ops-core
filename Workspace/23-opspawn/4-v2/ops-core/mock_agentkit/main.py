from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel

app = FastAPI()

class AgentInfo(BaseModel):
    agentId: str
    agentName: str
    version: str
    capabilities: List[str]
    contactEndpoint: str
    registrationTime: str
    metadata: Dict[str, Any]

agents: List[AgentInfo] = []

@app.post("/v1/agents")
async def register_agent(agent_info: AgentInfo):
    global agents
    agents.append(agent_info)
    return {"status": "success", "message": f"Agent {agent_info.agentId} registered"}

@app.get("/v1/agents")
async def list_agents():
    return {"status": "success", "message": "Agents retrieved successfully.", "data": agents}

@app.post("/v1/agents/{agentId}/run")
async def run_agent(agentId: str, payload: Dict[str, Any]):
    # In a real implementation, this would forward the payload to the agent's contactEndpoint
    print(f"Received task for agent {agentId}: {payload}")
    return {"status": "success", "message": f"Task dispatched to agent {agentId}"}