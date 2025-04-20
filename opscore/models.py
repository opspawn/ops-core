"""
Ops-Core Pydantic Models

Defines data structures used throughout the Ops-Core application,
particularly for API request/response validation and internal data representation.
"""

from pydantic import BaseModel, Field, HttpUrl, model_validator
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone # Import timezone
import uuid

# --- Agent Registration Models ---

class AgentRegistrationDetails(BaseModel):
    """Details provided when an agent registers (or discovered from AgentKit).""" # Corrected indentation (4 spaces)
    agentId: str # Unique ID for the agent (defined by AgentKit) # Corrected indentation (4 spaces)
    agentName: str # Corrected indentation (4 spaces)
    version: str # Corrected indentation (4 spaces)
    capabilities: List[str] = []
    contactEndpoint: HttpUrl # The agent's own API endpoint
    metadata: Dict[str, Any] = {}

class AgentInfo(AgentRegistrationDetails):
    """Internal representation of a registered agent."""
    agentId: str
    registrationTime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware

# --- Agent Notification Model (from AgentKit Webhook) ---

class AgentNotificationPayload(BaseModel):
   """Payload expected from AgentKit webhook for agent registration/deregistration."""
   event_type: str # e.g., "REGISTER", "DEREGISTER"
   agent_details: AgentRegistrationDetails

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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware

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
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware

# --- Session Models ---

class WorkflowSession(BaseModel):
    """Represents an execution instance of a workflow."""
    sessionId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflowId: str
    agentId: str # Initially targeted agent, might involve multiple later
    startTime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware
    last_updated_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware
    endTime: Optional[datetime] = None
    status: str = "started" # e.g., started, running, completed, failed, cancelled, paused
    metadata: Optional[Dict[str, Any]] = None # For storing arbitrary session-related data
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # Add tracking for current task, history, etc. if needed

class SessionUpdate(BaseModel):
    """Represents the data allowed for updating a session."""
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    end_time: Optional[datetime] = None
    # last_updated_time will be set automatically on update

# --- API Request/Response Models ---

class WorkflowTriggerRequest(BaseModel):
    """Payload for triggering a workflow."""
    workflowDefinitionId: Optional[str] = None
    workflowDefinition: Optional[WorkflowDefinition] = None # Allow inline definition
    initialPayload: Optional[Dict[str, Any]] = None # Optional data for the first task

    # Add validation to ensure either ID or definition is provided, but not both
    @model_validator(mode='before')
    @classmethod
    def check_definition_or_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'workflowDefinitionId' not in data and 'workflowDefinition' not in data:
                raise ValueError('Either workflowDefinitionId or workflowDefinition must be provided')
            if 'workflowDefinitionId' in data and data.get('workflowDefinitionId') and 'workflowDefinition' in data and data.get('workflowDefinition'):
                raise ValueError('Provide either workflowDefinitionId or workflowDefinition, not both')
        return data

class WorkflowTriggerResponse(BaseModel):
    """Response after successfully triggering a workflow."""
    sessionId: str
    workflowId: str
    message: str = "Workflow triggered successfully"

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