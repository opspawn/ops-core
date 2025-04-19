"""Data models for the Ops-Core SDK."""

from typing import TypedDict, Dict, Any, Optional, List

# --- State Update ---

class StateUpdatePayload(TypedDict):
    """Payload for updating an agent's state via the SDK."""
    state: str # e.g., "initializing", "idle", "active", "error", "finished"
    details: Optional[Dict[str, Any]]

# --- Workflow Trigger ---

class WorkflowTriggerPayload(TypedDict):
    """Payload for triggering a workflow via the SDK."""
    # Note: Only triggering by ID is supported initially. Inline definition omitted for simplicity.
    workflowDefinitionId: str
    initialPayload: Optional[Dict[str, Any]]

class WorkflowTriggerResponse(TypedDict):
    """Response received after triggering a workflow."""
    sessionId: str
    workflowId: str
    message: str

# --- Get State ---

class AgentStateResponse(TypedDict):
    """Response received when getting an agent's state."""
    agentId: str
    state: str
    details: Optional[Dict[str, Any]]
    timestamp: str # ISO 8601 format string

# --- General ---
# Potentially add simplified error response models if needed later