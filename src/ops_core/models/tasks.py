"""
Pydantic models for Task representation in ops-core.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, Union, TYPE_CHECKING

# Use SQLModel for database interaction
from sqlmodel import Field, SQLModel
# Import Column and JSON type for database-specific definitions
import sqlalchemy as sa # Added import
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON

# Import the shared MetaData instance from base
from .base import metadata

# Keep TaskStatus Enum
class TaskStatus(str, Enum):
    """Enum for possible task statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Function to generate string task IDs
def generate_task_id() -> str:
    """Generates a unique task ID string."""
    return f"task_{uuid.uuid4()}"

def current_utc_time() -> datetime:
    """Returns the current time in UTC."""
    return datetime.now(timezone.utc)


# Define the Task model using SQLModel for database interaction
class Task(SQLModel, table=True, metadata=metadata, __table_args__={'extend_existing': True}):
    """Represents a task managed by the ops-core scheduler, mapped to a database table."""
    # Use Field from SQLModel
    task_id: str = Field(default_factory=generate_task_id, primary_key=True, index=True)
    task_type: str = Field(index=True) # The type or category of the task (e.g., 'agent_run')
    name: Optional[str] = Field(default=None) # Optional human-readable name
    # Explicitly tell SQLAlchemy *not* to use native ENUM, map to VARCHAR
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True, sa_type=sa.Enum(TaskStatus, native_enum=False))
    created_at: datetime = Field(default_factory=current_utc_time, index=True, sa_type=sa.TIMESTAMP(timezone=True))
    updated_at: datetime = Field(default_factory=current_utc_time, sa_type=sa.TIMESTAMP(timezone=True))
    scheduled_at: Optional[datetime] = Field(default=None, sa_type=sa.TIMESTAMP(timezone=True)) # When the task is scheduled to run
    started_at: Optional[datetime] = Field(default=None, sa_type=sa.TIMESTAMP(timezone=True)) # When the task actually started
    completed_at: Optional[datetime] = Field(default=None, sa_type=sa.TIMESTAMP(timezone=True)) # When the task finished (completed, failed, or cancelled)

    # Use SQLAlchemy Column with JSON type for input_data and result
    # Type hints remain Dict/Any for Pydantic validation, but DB storage is JSON
    input_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    result: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    error_message: Optional[str] = Field(default=None) # Store error details if status is FAILED
    agent_id: Optional[str] = Field(default=None, index=True) # ID of the agentkit agent to execute, if applicable
    workflow_id: Optional[str] = Field(default=None, index=True) # ID of the parent workflow, if part of one

    # TODO: Consider adding priority, retries, dependencies, etc. later

    # Note: SQLModel handles Pydantic v2 config and serialization implicitly for DB interaction.
    # However, explicit serializers might be needed for specific JSON output formats.
    # Adding back serializer for consistent ISO format with 'Z'.
    from pydantic import field_serializer # Import if not already present

    @field_serializer('created_at', 'updated_at', 'scheduled_at', 'started_at', 'completed_at', when_used='json')
    def serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime objects to ISO format string with 'Z' for JSON."""
        if dt is None:
            return None
        # Ensure timezone is UTC before formatting
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             # Assuming naive datetimes are UTC, adjust if needed
             dt = dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo != timezone.utc:
             dt = dt.astimezone(timezone.utc)
        # Format with 'Z'
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


    # Keep the helper method for now, but its usage might change with the SQL store
    def update_status(self, new_status: TaskStatus, error_msg: Optional[str] = None):
        """Helper method to update task status and timestamps in the model instance."""
        self.status = new_status
        self.updated_at = current_utc_time()
        if new_status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = self.updated_at
        if new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.completed_at = self.updated_at
            if new_status == TaskStatus.FAILED:
                self.error_message = error_msg
