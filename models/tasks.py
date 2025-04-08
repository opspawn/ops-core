"""
Defines the core Task model and related enums for Ops-Core.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class TaskStatus(str, Enum):
    """
    Represents the possible statuses of a task.
    """
    # Ensure values are uppercase strings
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def current_utc_time() -> datetime:
    """Returns the current UTC time."""
    return datetime.now(timezone.utc)


class Task(BaseModel):
    """
    Represents a single task managed by Ops-Core.

    Attributes:
        task_id: Unique identifier for the task.
        name: Human-readable name for the task.
        task_type: The type of task (e.g., 'agent_run', 'data_processing').
        input_data: Dictionary containing the input data for the task.
        status: The current status of the task.
        created_at: Timestamp when the task was created.
        updated_at: Timestamp when the task was last updated.
        result: Optional dictionary containing the output/result of the task.
        error_message: Optional string containing error details if the task failed.
    """
    # Ensure arbitrary types are allowed for UUID input
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    task_id: UUID = Field(default_factory=uuid4)
    name: str
    task_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=current_utc_time)
    updated_at: datetime = Field(default_factory=current_utc_time)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Re-add field serializer for datetimes to ensure consistent ISO format output
    @field_serializer('created_at', 'updated_at', when_used='json')
    def serialize_dt_json(self, dt: datetime):
        return dt.isoformat()

    # Add serializer for TaskStatus to ensure uppercase string output
    @field_serializer('status', when_used='json')
    def serialize_status_json(self, status: TaskStatus):
        return status.value
