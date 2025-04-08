"""
In-memory implementation of the metadata store for Ops Core.

This provides a basic, non-persistent storage mechanism suitable for
development and testing purposes. It stores Task objects in a dictionary.
"""

import logging
from typing import Dict, List, Optional, Any # Added Any
from datetime import datetime, timezone # Added timezone

from ops_core.models import Task, TaskStatus # Import base models
from ops_core.models.tasks import current_utc_time # Import helper from specific module

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    """Exception raised when a task is not found in the store."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task with ID '{task_id}' not found.")


class InMemoryMetadataStore:
    """
    Manages Task metadata using an in-memory dictionary.

    This class provides basic CRUD operations for Task objects. It is not
    thread-safe and data is lost when the application stops.
    """

    def __init__(self):
        """Initializes the in-memory store with an empty dictionary."""
        self._tasks: Dict[str, Task] = {}
        logger.info("InMemoryMetadataStore initialized.")

    async def add_task(self, task: Task) -> None:
        """
        Adds a new task to the store.

        Args:
            task: The Task object to add.

        Raises:
            ValueError: If a task with the same ID already exists.
        """
        if task.task_id in self._tasks:
            logger.warning(f"Attempted to add duplicate task ID: {task.task_id}")
            raise ValueError(f"Task with ID '{task.task_id}' already exists.")
        self._tasks[task.task_id] = task.model_copy(deep=True)  # Store a copy
        logger.debug(f"Task added: {task.task_id}")

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a task by its ID.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            The Task object if found, otherwise None.
        """
        task = self._tasks.get(task_id)
        if task:
            logger.debug(f"Task retrieved: {task_id}")
            return task.model_copy(deep=True)  # Return a copy
        logger.debug(f"Task not found: {task_id}")
        return None

    async def update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        """
        Updates the status of an existing task.

        Args:
            task_id: The ID of the task to update.
            status: The new TaskStatus.

        Returns:
            The updated Task object.

        Raises:
            TaskNotFoundError: If the task with the given ID is not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Attempted to update status of non-existent task: {task_id}")
            raise TaskNotFoundError(task_id)

        # Update the status on the fetched task object.
        # The caller should have already updated other fields like output_data or error_message
        # on a task object before calling this, or used task.update_status().
        # This method primarily ensures the status field itself is updated in the store.
        task.status = status
        task.updated_at = current_utc_time() # Ensure updated_at is set
        # No need to replace the object, as 'task' is a reference to the object in the dict.
        # Modifications to 'task.status' and 'task.updated_at' directly affect the stored object.

        logger.info(f"Task status updated in store: {task_id} -> {status.name}")
        return task.model_copy(deep=True) # Return a copy of the updated task

    async def update_task_output(
        self,
        task_id: str,
        result: Optional[Any] = None, # Changed from output_data
        error_message: Optional[str] = None,
    ) -> Task:
        """
        Updates the result data and/or error message of an existing task,
        and sets the status accordingly (FAILED if error, COMPLETED if result).

        Args:
            task_id: The ID of the task to update.
            result: The new result data for the task.
            error_message: The new error message for the task.

        Returns:
            The updated Task object.

        Raises:
            TaskNotFoundError: If the task with the given ID is not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Attempted to update output of non-existent task: {task_id}")
            raise TaskNotFoundError(task_id)

        task.result = result # Changed from output_data
        task.error_message = error_message
        task.updated_at = current_utc_time() # Ensure updated_at is set

        # Update status based on outcome
        if error_message:
            task.status = TaskStatus.FAILED
            logger.info(f"Task {task_id} updated with error status.")
        elif result is not None: # Check if result is explicitly provided (even if None)
             # Consider if result being None should also mean completed? For now, require non-None result.
             # Let's assume any non-error result means completed for now.
            task.status = TaskStatus.COMPLETED
            logger.info(f"Task {task_id} updated with completed status.")
        # Else: Status remains unchanged if neither result nor error is provided? Or should default to COMPLETED?
        # Let's stick to explicit updates for now.

        logger.info(f"Task result/error updated in store: {task_id}")
        return task.model_copy(deep=True) # Return a copy of the updated task

    async def list_tasks(
        self, status_filter: Optional[TaskStatus] = None
    ) -> List[Task]:
        """
        Lists tasks currently in the store, optionally filtering by status.

        Args:
            status_filter: If provided, only tasks with this status are returned.

        Returns:
            A list of Task objects matching the criteria.
        """
        tasks = list(self._tasks.values())
        if status_filter:
            filtered_tasks = [
                task for task in tasks if task.status == status_filter
            ]
            logger.debug(
                f"Listed {len(filtered_tasks)} tasks with status {status_filter.name}"
            )
            # Return copies
            return [task.model_copy(deep=True) for task in filtered_tasks]
        else:
            logger.debug(f"Listed all {len(tasks)} tasks.")
            # Return copies
            return [task.model_copy(deep=True) for task in tasks]

    async def delete_task(self, task_id: str) -> bool:
        """
        Deletes a task from the store.

        Args:
            task_id: The ID of the task to delete.

        Returns:
            True if the task was deleted, False if it was not found.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Task deleted: {task_id}")
            return True
        logger.warning(f"Attempted to delete non-existent task: {task_id}")
        return False
