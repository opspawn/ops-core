"""
Pydantic schemas for the Tasks API endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict # Import ConfigDict
from datetime import datetime

from ops_core.models.tasks import TaskStatus  # Import from core models


# --- Request Schemas ---

class TaskCreateRequest(BaseModel):
    """
    Schema for creating a new task via the API.
    """
    task_type: str = Field(..., description="Type identifier for the task.")
    input_data: Dict[str, Any] = Field(
        default_factory=dict, description="Input data required for the task."
    )
    # Add other fields if needed, e.g., priority, specific agent config


# --- Response Schemas ---

class TaskResponse(BaseModel):
    """
    Schema for representing a task in API responses.
    Maps closely to the core Task model but can be adjusted for API needs.
    """
    task_id: str
    task_type: str
    status: TaskStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Use model_config = ConfigDict instead of class Config
    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """
    Schema for returning a list of tasks.
    """
    tasks: List[TaskResponse]
    total: int
