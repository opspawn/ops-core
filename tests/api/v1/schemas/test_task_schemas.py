"""
Unit tests for the Pydantic schemas defined in ops_core.api.v1.schemas.tasks.
"""

import pytest
from pydantic import ValidationError
from datetime import datetime
import uuid

from ops_core.api.v1.schemas.tasks import (
    TaskCreateRequest,
    TaskResponse,
    TaskListResponse,
    # TaskBase, # This class is not defined/exported in the schema file
)
from ops_core.models.tasks import TaskStatus # Import enum for validation


# --- Tests for TaskCreateRequest ---

def test_task_create_request_valid():
    """Test TaskCreateRequest with valid data."""
    data = {"task_type": "agent_run", "input_data": {"goal": "test goal"}}
    try:
        request = TaskCreateRequest(**data)
        assert request.task_type == "agent_run"
        assert request.input_data == {"goal": "test goal"}
    except ValidationError as e:
        pytest.fail(f"Valid TaskCreateRequest failed validation: {e}")

def test_task_create_request_missing_task_type():
    """Test TaskCreateRequest validation fails if task_type is missing."""
    data = {"input_data": {"goal": "test goal"}}
    with pytest.raises(ValidationError) as excinfo:
        TaskCreateRequest(**data)
    assert "task_type" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)

def test_task_create_request_invalid_input_data_type():
    """Test TaskCreateRequest validation fails if input_data is not a dict."""
    data = {"task_type": "agent_run", "input_data": "not a dict"}
    with pytest.raises(ValidationError) as excinfo:
        TaskCreateRequest(**data)
    assert "input_data" in str(excinfo.value)
    assert "Input should be a valid dictionary" in str(excinfo.value)

def test_task_create_request_input_data_optional():
    """Test TaskCreateRequest validation passes if input_data is omitted (optional)."""
    # Test case where input_data key is missing entirely
    data_missing = {"task_type": "simple_task"}
    try:
        request_missing = TaskCreateRequest(**data_missing)
        assert request_missing.task_type == "simple_task"
        assert request_missing.input_data == {} # Default seems to be {} not None
    except ValidationError as e:
        pytest.fail(f"TaskCreateRequest missing input_data failed validation: {e}")


# --- Tests for TaskResponse ---
# Primarily testing serialization/model creation, less complex validation here

def test_task_response_valid():
    """Test creating a TaskResponse model."""
    task_id = str(uuid.uuid4())
    now = datetime.now()
    data = {
        "task_id": task_id,
        "task_type": "agent_run",
        "status": TaskStatus.COMPLETED,
        "input_data": {"goal": "completed goal"},
        "output_data": {"result": "success"},
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        response = TaskResponse(**data)
        assert response.task_id == task_id
        assert response.status == TaskStatus.COMPLETED
        assert response.output_data == {"result": "success"}
        assert response.created_at == now
    except ValidationError as e:
        pytest.fail(f"Valid TaskResponse failed validation: {e}")

def test_task_response_status_enum():
    """Test TaskResponse correctly handles the TaskStatus enum."""
    task_id = str(uuid.uuid4())
    now = datetime.now()
    data = {
        "task_id": task_id,
        "task_type": "agent_run",
        "status": "completed", # Use string value
        "input_data": {}, # Change None to {} as it seems required
        "created_at": now,
        "updated_at": now,
    }
    response = TaskResponse(**data)
    assert response.status == TaskStatus.COMPLETED # Should convert to enum member

    data_invalid = {
        "task_id": task_id,
        "task_type": "agent_run",
        "status": "invalid_status", # Invalid enum value
        "input_data": {}, # Change None to {} as it seems required
        "created_at": now,
        "updated_at": now,
    }
    with pytest.raises(ValidationError) as excinfo:
        TaskResponse(**data_invalid)
    assert "status" in str(excinfo.value)
    assert "Input should be 'pending', 'running', 'completed', 'failed' or 'cancelled'" in str(excinfo.value)


# --- Tests for TaskListResponse ---

def test_task_list_response_valid():
    """Test creating a TaskListResponse model."""
    task_id1 = str(uuid.uuid4())
    task_id2 = str(uuid.uuid4())
    now = datetime.now()
    task1_data = {
        "task_id": task_id1, "task_type": "t1", "status": TaskStatus.PENDING,
        "input_data": {"a": 1}, # Add missing required field
        "created_at": now, "updated_at": now,
    }
    task2_data = {
        "task_id": task_id2, "task_type": "t2", "status": TaskStatus.RUNNING,
        "input_data": {}, # Change None to {} as it seems required
        "created_at": now, "updated_at": now,
    }
    task1 = TaskResponse(**task1_data)
    task2 = TaskResponse(**task2_data)

    list_data = {"tasks": [task1, task2], "total": 2} # Add missing 'total' field
    try:
        list_response = TaskListResponse(**list_data)
        assert len(list_response.tasks) == 2
        assert list_response.tasks[0].task_id == task_id1
        assert list_response.tasks[1].status == TaskStatus.RUNNING
    except ValidationError as e:
        pytest.fail(f"Valid TaskListResponse failed validation: {e}")

def test_task_list_response_empty():
    """Test TaskListResponse with an empty list."""
    list_data = {"tasks": [], "total": 0} # Add missing 'total' field
    try:
        list_response = TaskListResponse(**list_data)
        assert len(list_response.tasks) == 0
    except ValidationError as e:
        pytest.fail(f"TaskListResponse with empty list failed validation: {e}")

def test_task_list_response_invalid_item_type():
    """Test TaskListResponse validation fails if list contains non-TaskResponse items."""
    # Add missing 'total' field which likely causes the initial failure
    list_data = {"tasks": [{"id": "not a task response"}, 123], "total": 2}
    with pytest.raises(ValidationError) as excinfo:
        TaskListResponse(**list_data)
    # Check that the validation error mentions the 'tasks' field
    # and indicates issues with the items within the list (e.g., missing fields or wrong type)
    error_str = str(excinfo.value)
    assert "tasks" in error_str
    # Check for errors related to list items, e.g., tasks.0 or tasks.1
    assert "tasks.0" in error_str or "tasks.1" in error_str
    # Check for common Pydantic error types related to list item validation
    assert "Field required" in error_str or "Model expected" in error_str or "Input should be a valid dictionary" in error_str
