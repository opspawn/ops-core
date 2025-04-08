"""
In-memory implementation of the task scheduler engine for Ops-Core.

Note: This MVP implementation only submits tasks to the metadata store.
It does not yet handle actual task execution or asynchronous processing
(which was previously handled by Dramatiq integration in Task 3.4).
"""

from typing import Any, Dict

from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.models.tasks import Task


class InMemoryScheduler:
    """
    An in-memory scheduler that submits tasks to a metadata store.
    """
    # TODO: Re-integrate mcp_client and Dramatiq broker dependencies later
    # when tackling Tasks 2.12 and re-validating Task 3.4.
    # For MVP Task 2.1, only metadata_store is needed.
    def __init__(self, metadata_store: InMemoryMetadataStore):
        """
        Initializes the InMemoryScheduler (MVP version).

        Args:
            metadata_store: An instance of InMemoryMetadataStore to manage task state.
        """
        self._metadata_store = metadata_store

    def submit_task(
        self, name: str, task_type: str, input_data: Dict[str, Any]
    ) -> Task:
        """
        Creates a new task and adds it to the metadata store.

        Args:
            name: The human-readable name for the task.
            task_type: The type of task (e.g., 'agent_run').
            input_data: A dictionary containing the input data for the task.

        Returns:
            The newly created Task object.
        """
        # Create the task object
        new_task = Task(
            name=name,
            task_type=task_type,
            input_data=input_data,
            # Status defaults to PENDING, created_at/updated_at default to now
        )

        # Add the task to the metadata store
        self._metadata_store.add_task(new_task)

        # Return a copy of the task as stored
        # Reason: Ensures the returned object reflects the state in the store
        # and prevents external modification of the stored object via the return value.
        stored_task = self._metadata_store.get_task(new_task.task_id)
        if stored_task is None:
             # This should theoretically never happen if add_task succeeded
             raise RuntimeError(f"Failed to retrieve task {new_task.task_id} immediately after adding.") # pragma: no cover

        return stored_task
