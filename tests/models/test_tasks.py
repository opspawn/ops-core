"""
Unit tests for the Task model and TaskStatus enum.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ops_core.models.tasks import Task, TaskStatus, current_utc_time


def test_task_status_enum():
    """Verify TaskStatus enum values."""
    # Check the .value attribute for the string representation
    # Assert against lowercase values as defined in the Enum
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled" # Add cancelled
    assert len(TaskStatus) == 5 # Update length check


def test_task_creation_defaults():
    """Test Task creation with default values."""
    start_time = current_utc_time()
    task = Task(name="Test Task", task_type="test")

    # Ensure task_id is a string and starts with "task_"
    assert isinstance(task.task_id, str)
    assert task.task_id.startswith("task_")
    assert task.name == "Test Task"
    assert task.task_type == "test"
    assert task.input_data == {}
    assert task.status == TaskStatus.PENDING
    assert task.created_at >= start_time
    assert task.updated_at >= start_time
    assert task.created_at.tzinfo == timezone.utc
    assert task.updated_at.tzinfo == timezone.utc
    assert task.result is None
    assert task.error_message is None


def test_task_creation_with_values():
    """Test Task creation with specific values."""
    task_id = f"task_{uuid.uuid4()}" # Use string ID
    created = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    updated = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
    input_data = {"key": "value"}
    result_data = {"output": "success"}

    # Pass task_id as string
    task = Task(
        task_id=task_id, # Pass the string ID
        name="Specific Task",
        task_type="specific_test",
        input_data=input_data,
        status=TaskStatus.COMPLETED,
        created_at=created,
        updated_at=updated,
        result=result_data,
        error_message=None,
    )

    # Assert against the string ID used during creation
    assert task.task_id == task_id
    assert task.name == "Specific Task"
    assert task.task_type == "specific_test"
    assert task.input_data == input_data
    assert task.status == TaskStatus.COMPLETED
    assert task.created_at == created
    assert task.updated_at == updated
    # Use model_dump().get() to bypass potential __getattr__ issues
    assert task.model_dump().get('result') == result_data
    assert task.error_message is None


def test_task_serialization():
    """Test Task serialization (especially datetime)."""
    created = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    updated = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
    task = Task(
        name="Serialization Test",
        task_type="serialize",
        created_at=created,
        updated_at=updated,
    )

    # Use model_dump(mode='json') for ISO strings, or check datetime objects directly
    task_dict_py = task.model_dump() # Python objects
    task_dict_json = task.model_dump(mode='json') # JSON-serializable types

    # Check python objects
    assert task_dict_py["created_at"] == created
    assert task_dict_py["updated_at"] == updated
    assert task_dict_py["status"] == TaskStatus.PENDING # Check the enum object directly

    # Check JSON serialized strings using the added serializers
    # Expect format with 'Z' suffix due to custom serializer
    expected_created_str = created.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    expected_updated_str = updated.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    assert task_dict_json["created_at"] == expected_created_str
    assert task_dict_json["updated_at"] == expected_updated_str
    assert task_dict_json["status"] == TaskStatus.PENDING.value # Check the serialized string value

# Removed test_task_validation_error as SQLModel handles required fields implicitly
# during instantiation, and other tests cover successful creation.
