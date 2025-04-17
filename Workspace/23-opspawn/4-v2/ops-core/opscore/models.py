"""
Ops-Core Pydantic Models

Defines data structures used throughout the Ops-Core application,
particularly for API request/response validation and internal data representation.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, Any, Optional, List
from datetime import datetime

# --- Agent Registration Models ---

class AgentRegistrationDetails(BaseModel):
    """Details provided when an agent registers (or discovered from AgentKit)."""
    agentName: str
    version: str
    capabilities: List[str] = []
    contactEndpoint: HttpUrl # The agent's own API endpoint
    metadata: Dict[str, Any] = {}

class AgentInfo(AgentRegistrationDetails):
    """Internal representation of a registered agent."""
    agentId: str
    registrationTime: datetime = Field(default_factory=datetime.utcnow)

# --- Agent State Models ---

class AgentStateUpdatePayload(BaseModel):
    """Payload expected from AgentKit SDK for state updates."""
    agentId: str
    timestamp: str # ISO 8601 format string - validation/parsing needed
    state: str # e.g., "initializing", "idle", "active", "error", "finished"
    details: Optional[Dict[str, Any]] = None

class AgentState(BaseModel):
    """Internal representation of an agent's state at a point in time."""
    agentId: str
    state: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --- Workflow Models ---

class WorkflowDefinition(BaseModel):
    """Structure for a workflow definition (loaded from JSON/YAML)."""
    id: str # Unique ID for the workflow
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    tasks: List[Dict[str, Any]] # Define task structure more specifically later
    # Example task structure:
    # tasks: [
    #   {"taskId": "task1", "name": "...", "agentCapability": "...", "parameters": {...}, "nextTaskId": "task2"},
    #   {"taskId": "task2", "name": "...", ...}
    # ]

class Task(BaseModel):
    """Represents a task instance to be executed."""
    taskId: str # Unique ID for this task instance
    workflowId: str
    sessionId: str
    agentId: str # Target agent for this task
    taskDefinitionId: str # ID of the task from the WorkflowDefinition
    payload: Dict[str, Any] # Parameters/data for the task
    status: str = "pending" # e.g., pending, dispatched, running, completed, failed
    retryCount: int = 0
    maxRetries: int = 3 # Could come from workflow definition
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

# --- Session Models ---

class WorkflowSession(BaseModel):
    """Represents an execution instance of a workflow."""
    sessionId: str
    workflowId: str
    agentId: str # Initially targeted agent, might involve multiple later
    startTime: datetime = Field(default_factory=datetime.utcnow)
    endTime: Optional[datetime] = None
    status: str # e.g., started, running, completed, failed, cancelled
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # Add tracking for current task, history, etc. if needed

# --- API Response Models ---

class StatusResponse(BaseModel):
    """Generic success/status response."""
    status: str = "success"
    message: Optional[str] = None

class ErrorDetail(BaseModel):
    """Standard structure for error details in API responses."""
    code: Optional[str] = None # Application-specific error code
    message: str

class ErrorResponse(BaseModel):
    """Standard structure for API error responses."""
    detail: ErrorDetail | str # Allow simple string or detailed object

# Add other models as needed (e.g., for configuration, specific API payloads)