"""
Pydantic models for Task representation in ops-core.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_serializer, ConfigDict

class TaskStatus(str, Enum):
    """Enum for possible task statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

def generate_task_id() -> str:
    """Generates a unique task ID."""
    return f"task_{uuid.uuid4()}"

def current_utc_time() -> datetime:
    """Returns the current time in UTC."""
    return datetime.now(timezone.utc)

class Task(BaseModel):
    """Represents a task managed by the ops-core scheduler."""
    task_id: str = Field(default_factory=generate_task_id)
    task_type: str # The type or category of the task (e.g., 'agent_run')
    name: Optional[str] = None # Optional human-readable name
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=current_utc_time)
    updated_at: datetime = Field(default_factory=current_utc_time)
    scheduled_at: Optional[datetime] = None # When the task is scheduled to run
    started_at: Optional[datetime] = None # When the task actually started
    completed_at: Optional[datetime] = None # When the task finished (completed, failed, or cancelled)
    input_data: Optional[Dict[str, Any]] = None # Input parameters for the task
    output_data: Optional[Any] = None # Result or output of the task (can be any type)
    error_message: Optional[str] = None # Store error details if status is FAILED
    agent_id: Optional[str] = None # ID of the agentkit agent to execute, if applicable
    workflow_id: Optional[str] = None # ID of the parent workflow, if part of one

    # TODO: Consider adding priority, retries, dependencies, etc. later

    # Pydantic v2 configuration using ConfigDict (replaces class Config)
    # Note: use_enum_values=True is the default in v2, so no need to specify.
    model_config = ConfigDict(
        # Allow extra fields if needed, though usually better to be explicit
        # extra='allow',
    )

    # Pydantic v2 custom serializers using @field_serializer (replaces json_encoders)
    @field_serializer('created_at', 'updated_at', 'scheduled_at', 'started_at', 'completed_at', when_used='json')
    def serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime objects to ISO format string for JSON."""
        return dt.isoformat() if dt else None

    def update_status(self, new_status: TaskStatus, error_msg: Optional[str] = None):
        """Helper method to update task status and timestamps."""
        self.status = new_status
        self.updated_at = current_utc_time()
        if new_status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = self.updated_at
        if new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.completed_at = self.updated_at
            if new_status == TaskStatus.FAILED:
                self.error_message = error_msg
