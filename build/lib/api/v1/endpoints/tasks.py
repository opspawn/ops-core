"""
API Endpoints for managing Tasks.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.store import InMemoryMetadataStore # Removed BaseMetadataStore import
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.models.tasks import Task
from ..schemas.tasks import TaskCreateRequest, TaskResponse, TaskListResponse

# --- Global instances (simple approach for now, created lazily) ---
# These will be created on first request if not overridden by tests
_metadata_store: Optional[InMemoryMetadataStore] = None
_mcp_client: Optional[OpsMcpClient] = None
_scheduler: Optional[InMemoryScheduler] = None

# --- Dependencies ---

# Dependency function to get the metadata store instance
def get_metadata_store() -> InMemoryMetadataStore: # Changed type hint
    """
    Provides the metadata store instance. Creates it if it doesn't exist.
    """
    global _metadata_store
    if _metadata_store is None:
        # In a real app, this might load from config or be part of a larger context
        print("Creating singleton InMemoryMetadataStore instance") # Debug print
        _metadata_store = InMemoryMetadataStore()
    return _metadata_store

# Dependency function to get the MCP client instance
def get_mcp_client() -> OpsMcpClient:
    """
    Provides the MCP client instance. Creates it if it doesn't exist.
    """
    global _mcp_client
    if _mcp_client is None:
        # This will load config automatically based on OpsMcpClient implementation
        print("Creating singleton OpsMcpClient instance") # Debug print
        _mcp_client = OpsMcpClient()
        # TODO: Consider starting servers if needed, or handle this in app lifespan
    return _mcp_client

# Dependency function to get the scheduler instance
def get_scheduler(
    metadata_store: InMemoryMetadataStore = Depends(get_metadata_store), # Corrected type hint
    mcp_client: OpsMcpClient = Depends(get_mcp_client)
) -> InMemoryScheduler:
    """
    Provides the scheduler instance. Creates it if it doesn't exist.
    Requires metadata_store and mcp_client dependencies.
    """
    global _scheduler
    if _scheduler is None:
        print(f"Creating singleton InMemoryScheduler instance with store: {metadata_store} and client: {mcp_client}") # Debug print
        _scheduler = InMemoryScheduler(metadata_store=metadata_store, mcp_client=mcp_client)
        # TODO: Consider starting scheduler loop if needed, or handle in app lifespan
    return _scheduler


# --- Router ---
router = APIRouter()


# --- Endpoints ---

@router.post(
    "/tasks/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new task",
    description="Submits a new task to the scheduler for execution.",
)
async def create_task(
    task_request: TaskCreateRequest,
    scheduler: InMemoryScheduler = Depends(get_scheduler),
) -> Task:
    """
    Submits a new task to the scheduler.

    Args:
        task_request: The details of the task to create.
        scheduler: The scheduler instance (injected dependency).

    Returns:
        The created Task object.
    """
    # Reason: Generate a default name and use the scheduler's submit method.
    try:
        # Generate a default name if not provided in the request (schema doesn't have it yet)
        task_name = f"API Task - {task_request.task_type}"
        task = await scheduler.submit_task(
            name=task_name, # Pass the generated name
            task_type=task_request.task_type,
            input_data=task_request.input_data,
        )
        return task
    except Exception as e:
        # TODO: Add more specific error handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {e}",
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get task status",
    description="Retrieves the details and status of a specific task by its ID.",
)
async def get_task(
    task_id: str,
    metadata_store: InMemoryMetadataStore = Depends(get_metadata_store),
) -> Task:
    """
    Retrieves a specific task by its ID.

    Args:
        task_id: The ID of the task to retrieve.
        metadata_store: The metadata store instance (injected dependency).

    Returns:
        The requested Task object.

    Raises:
        HTTPException: If the task with the given ID is not found.
    """
    # Reason: Use the metadata store to fetch the task details.
    task = await metadata_store.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )
    return task


@router.get(
    "/tasks/",
    response_model=TaskListResponse,
    summary="List all tasks",
    description="Retrieves a list of all tasks known to the system.",
)
async def list_tasks(
    metadata_store: InMemoryMetadataStore = Depends(get_metadata_store),
    # TODO: Add pagination parameters (skip, limit)
) -> TaskListResponse:
    """
    Retrieves a list of all tasks.

    Args:
        metadata_store: The metadata store instance (injected dependency).

    Returns:
        A response object containing the list of tasks and the total count.
    """
    # Reason: Use the metadata store to get all tasks. Pagination should be added later.
    tasks = await metadata_store.list_tasks()
    return TaskListResponse(tasks=tasks, total=len(tasks))
