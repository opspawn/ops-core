import pytest
from datetime import datetime, timezone, timedelta
from pydantic import TypeAdapter

from ops_core.models.tasks import Task, TaskStatus


def test_task_model_serialization_with_datetime():
    """
    Test that the Task model correctly serializes datetime fields to ISO 8601 strings.
    """
    now = datetime.now(timezone.utc)
    task_data = {
        "task_id": "task-123",
        "name": "Test Task",
        "task_type": "agent_run",
        "status": TaskStatus.PENDING,
        "input_data": {"prompt": "hello"},
        "created_at": now,
        "updated_at": now + timedelta(seconds=10),
        "result": None,
        "error": None,
        "scheduled_at": None,
        "started_at": None,
        "completed_at": None,
        "metadata": {},
    }
    task = Task(**task_data)

    # Use TypeAdapter for serialization as recommended in Pydantic v2
    TaskAdapter = TypeAdapter(Task)
    serialized_task = TaskAdapter.dump_python(task) # dump_python keeps python types

    # Check if datetime fields remain datetime objects after dump_python
    assert isinstance(serialized_task["created_at"], datetime)
    assert isinstance(serialized_task["updated_at"], datetime)
    # Check the values directly
    assert serialized_task["created_at"] == now
    assert serialized_task["updated_at"] == now + timedelta(seconds=10)
    assert serialized_task["scheduled_at"] is None
    assert serialized_task["started_at"] is None
    assert serialized_task["completed_at"] is None

    # To test JSON serialization (which should produce strings), use model_dump
    json_serializable_dict = task.model_dump(mode='json')
    assert isinstance(json_serializable_dict["created_at"], str)
    assert isinstance(json_serializable_dict["updated_at"], str)
    # Allow for both Z and +00:00 UTC representation by comparing up to the timezone part
    assert json_serializable_dict["created_at"].startswith(now.isoformat().split('+')[0])
    assert json_serializable_dict["updated_at"].startswith((now + timedelta(seconds=10)).isoformat().split('+')[0])
    assert json_serializable_dict["created_at"].endswith(('Z', '+00:00'))
    assert json_serializable_dict["updated_at"].endswith(('Z', '+00:00'))


def test_task_model_deserialization_with_datetime_str():
    """
    Test that the Task model correctly deserializes ISO 8601 strings to datetime objects.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    later_str = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    serialized_data = {
        "task_id": "task-456",
        "name": "Deserialize Test",
        "task_type": "simple_echo",
        "status": TaskStatus.COMPLETED,
        "input_data": {"message": "test"},
        "created_at": now_str,
        "updated_at": later_str,
        "result": {"echo": "test"},
        "error": None,
        "scheduled_at": None,
        "started_at": now_str, # Example: started at creation time
        "completed_at": later_str, # Example: completed at update time
        "metadata": {"run_id": "abc"},
    }

    TaskAdapter = TypeAdapter(Task)
    task = TaskAdapter.validate_python(serialized_data)

    # Check if string fields were deserialized to datetime objects
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)
    assert isinstance(task.started_at, datetime)
    assert isinstance(task.completed_at, datetime)

    # Check if the values match (allowing for potential precision differences in parsing)
    # Pydantic should handle parsing the ISO string back correctly
    assert task.created_at.isoformat() == now_str
    assert task.updated_at.isoformat() == later_str
    assert task.started_at.isoformat() == now_str
    assert task.completed_at.isoformat() == later_str

    # Ensure timezone info is present (UTC)
    assert task.created_at.tzinfo == timezone.utc
    assert task.updated_at.tzinfo == timezone.utc
    assert task.started_at.tzinfo == timezone.utc
    assert task.completed_at.tzinfo == timezone.utc


def test_task_model_optional_datetimes_none():
    """
    Test serialization and deserialization when optional datetime fields are None.
    """
    now = datetime.now(timezone.utc)
    task_data = {
        "task_id": "task-789",
        "name": "Optional None Test",
        "task_type": "agent_run",
        "status": TaskStatus.PENDING,
        "input_data": {"prompt": "another"},
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
        "scheduled_at": None,
        "started_at": None,
        "completed_at": None,
        "metadata": {},
    }
    task = Task(**task_data)

    TaskAdapter = TypeAdapter(Task)
    serialized_task = TaskAdapter.dump_python(task)
    deserialized_task = TaskAdapter.validate_python(serialized_task)

    assert serialized_task["scheduled_at"] is None
    assert serialized_task["started_at"] is None
    assert serialized_task["completed_at"] is None

    assert deserialized_task.scheduled_at is None
    assert deserialized_task.started_at is None
    assert deserialized_task.completed_at is None
