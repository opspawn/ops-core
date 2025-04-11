from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict # Import Dict

from ops_core.models.tasks import Task, TaskStatus # Corrected import path


# --- Custom Exceptions ---
class TaskNotFoundError(Exception):
    """Raised when a task with the specified ID is not found."""
    pass

class TaskExistsError(Exception):
    """Raised when attempting to add a task that already exists."""
    pass


class BaseMetadataStore(ABC):
    """Abstract base class for metadata storage."""

    @abstractmethod
    async def add_task(self, task: Task) -> None:
        """
        Adds a new task to the store.

        Args:
            task: The Task object to add.

        Raises:
            TaskExistsError: If a task with the same ID already exists.
        """
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a task by its ID.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            The Task object if found, otherwise None.
        """
        pass

    @abstractmethod
    async def list_tasks(
        self, limit: int = 100, offset: int = 0
    ) -> List[Task]:
        """
        Lists tasks, potentially with pagination.

        Args:
            limit: Maximum number of tasks to return.
            offset: Number of tasks to skip.

        Returns:
            A list of Task objects.
        """
        pass

    @abstractmethod
    async def update_task_status(
        self, task_id: str, status: TaskStatus
    ) -> Optional[Task]:
        """
        Updates the status of an existing task.

        Args:
            task_id: The ID of the task to update.
            status: The new TaskStatus.

        Returns:
            The updated Task object if found and updated, otherwise None.

        Raises:
            TaskNotFoundError: If the task with the given ID does not exist.
        """
        pass

    @abstractmethod
    async def update_task_output(
        self, task_id: str, result: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        """
        Updates the output/result of a completed or failed task.

        Args:
            task_id: The ID of the task to update.
            result: The output data dictionary.

        Returns:
            The updated Task object if found and updated, otherwise None.

        Raises:
            TaskNotFoundError: If the task with the given ID does not exist.
        """
        pass

    # Optional: Add methods for deleting or other operations if needed later
    # @abstractmethod
    # async def delete_task(self, task_id: str) -> bool:
    #     """Deletes a task by its ID."""
    #     pass
