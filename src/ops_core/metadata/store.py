"""
Defines the abstract base class for metadata stores and custom exceptions.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any

from ops_core.models.tasks import Task, TaskStatus # Corrected import path

class TaskNotFoundError(Exception):
    """Custom exception raised when a task is not found in the store."""
    pass

class BaseMetadataStore(ABC):
    """Abstract base class for metadata storage."""

    @abstractmethod
    async def add_task(self, task: Task) -> Task:
        """Adds a new task to the store."""
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Task:
        """Retrieves a task by its ID. Raises TaskNotFoundError if not found."""
        pass

    @abstractmethod
    async def update_task_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None) -> Task:
        """Updates the status of an existing task. Raises TaskNotFoundError if not found."""
        pass

    @abstractmethod
    async def update_task_output(self, task_id: str, result: Any) -> Task:
        """Updates the output data of a completed task. Raises TaskNotFoundError if not found."""
        pass

    @abstractmethod
    async def list_tasks(self, limit: int = 100, offset: int = 0, status: Optional[TaskStatus] = None) -> List[Task]:
        """Lists tasks, optionally filtering by status."""
        pass

# --- InMemoryMetadataStore Implementation (Restored) ---
# Kept for compatibility with existing tests that might use the mock fixture.

from copy import deepcopy
from typing import Dict

class InMemoryMetadataStore(BaseMetadataStore):
    """In-memory implementation of the metadata store (for testing/mocking)."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}

    async def add_task(self, task: Task) -> Task:
        """Adds a new task to the in-memory store."""
        if task.task_id in self._tasks:
            raise ValueError(f"Task with ID '{task.task_id}' already exists.")
        # Store a deep copy to prevent external modifications
        task_copy = deepcopy(task)
        self._tasks[task.task_id] = task_copy
        # Return another deep copy consistent with get_task behavior
        return deepcopy(task_copy)

    async def get_task(self, task_id: str) -> Task:
        """Retrieves a task by its ID from memory."""
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
        # Return a deep copy to prevent external modifications
        return deepcopy(task)

    async def update_task_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None) -> Task:
        """Updates the status of an existing task in memory."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task with ID '{task_id}' not found for status update.")

        # Get the stored task (it's already a copy)
        task_to_update = self._tasks[task_id]
        # Use the model's helper method
        task_to_update.update_status(status, error_message)
        # Store the updated copy
        self._tasks[task_id] = task_to_update
        # Return a new deep copy
        return deepcopy(task_to_update)

    async def update_task_output(self, task_id: str, result: Any = None, error_message: Optional[str] = None) -> Task:
        """Updates the output data/error of a completed task in memory."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(f"Task with ID '{task_id}' not found for output update.")

        task_to_update = self._tasks[task_id]
        task_to_update.result = result
        task_to_update.error_message = error_message
        # Determine final status based on error
        final_status = TaskStatus.FAILED if error_message else TaskStatus.COMPLETED
        task_to_update.update_status(final_status, error_message) # Update status and timestamps

        self._tasks[task_id] = task_to_update
        return deepcopy(task_to_update)

    async def list_tasks(self, limit: int = 100, offset: int = 0, status: Optional[TaskStatus] = None) -> List[Task]:
        """Lists tasks from memory, optionally filtering by status."""
        # Sort by created_at descending to mimic DB behavior (optional, but good practice)
        sorted_tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

        filtered_tasks: List[Task] = []
        if status:
            for task in sorted_tasks:
                if task.status == status:
                    filtered_tasks.append(task)
        else:
            filtered_tasks = sorted_tasks

        # Apply limit and offset
        paginated_tasks = filtered_tasks[offset : offset + limit]

        # Return deep copies
        return [deepcopy(task) for task in paginated_tasks]

# Note: Focusing on SqlMetadataStore for primary implementation.
# InMemory version kept for potential test compatibility.
