"""
In-memory implementation of the metadata store for Ops-Core tasks.

Note: This implementation is not persistent and not thread-safe.
Suitable for MVP and testing purposes only.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ops_core.models.tasks import Task, TaskStatus, current_utc_time


class InMemoryMetadataStore:
    """
    An in-memory store for managing Task metadata.
    """

    def __init__(self):
        """Initializes the in-memory store."""
        self._store: Dict[UUID, Task] = {}
        # Note: Even though methods are async, the internal storage is sync.

    async def add_task(self, task: Task) -> None:
        """
        Adds a new task to the store.

        Args:
            task: The Task object to add.
        """
        if task.task_id in self._store:
            # Ensure the error message matches the test expectation precisely
            raise ValueError(f"Task with ID '{task.task_id}' already exists.")
        self._store[task.task_id] = task.model_copy(deep=True)
        # Reason: Store a copy to prevent external modifications affecting the store

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """
        Retrieves a task by its ID.

        Args:
            task_id: The UUID of the task to retrieve.

        Returns:
            The Task object if found, otherwise None.
        """
        task = self._store.get(task_id)
        return task.model_copy(deep=True) if task else None
        # Reason: Return a copy to prevent external modifications

    async def update_task_status(self, task_id: UUID, status: TaskStatus) -> Optional[Task]:
        """
        Updates the status of an existing task.

        Args:
            task_id: The UUID of the task to update.
            status: The new TaskStatus.

        Returns:
            The updated Task object if found, otherwise None.
        """
        task = self._store.get(task_id)
        if not task:
            # Return None if task not found, as per original implementation and test expectation
            return None
        if task: # This 'if task:' is now redundant due to the check above, but keep for clarity
            now = current_utc_time()
            updated_fields = {"status": status, "updated_at": now}
            updated_task = task.model_copy(update=updated_fields)
            self._store[task_id] = updated_task
            return updated_task.model_copy(deep=True)
            # Reason: Return a copy
        # Return None if task was not found (already handled above)
        return None # This line is effectively unreachable now but kept for structure

    async def update_task_output(
        self,
        task_id: UUID,
        # Corrected signature with single parameters
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Updates the result or error message of a completed or failed task.

        Also updates the 'updated_at' timestamp.

        Args:
            task_id: The UUID of the task to update.
            result: The result dictionary (for completed tasks).
            error_message: The error message string (for failed tasks).

        Returns:
            The updated Task object if found, otherwise None.
        """
        task = self._store.get(task_id)
        if not task:
             return None # Return None if task not found

        # Proceed if task exists
        now = current_utc_time()
        updated_fields = {
            # Ensure result is explicitly set, even if None when error occurs
            "result": result, # Store result regardless of error for potential inspection
            "error_message": error_message,
            "updated_at": now, # Corrected indentation
        }
        # Ensure status reflects completion/failure if output is set
        if error_message is not None and task.status != TaskStatus.FAILED:
            updated_fields["status"] = TaskStatus.FAILED
        elif result is not None and task.status != TaskStatus.COMPLETED:
             updated_fields["status"] = TaskStatus.COMPLETED

        updated_task = task.model_copy(update=updated_fields)
        # Correct indentation for the following lines
        self._store[task_id] = updated_task
        return updated_task.model_copy(deep=True)
        # Reason: Return a copy
        # The 'return None' below is unreachable if task was found, but kept for structure clarity
        # return None

    async def list_tasks(self) -> List[Task]:
        """
        Lists all tasks currently in the store.

        Returns:
            A list of all Task objects.
        """
        # Return copies to prevent external modification
        return [task.model_copy(deep=True) for task in self._store.values()]
