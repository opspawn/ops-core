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
router = APIRouter(
    # prefix="/v1", # Prefix is handled when including the router in main.py
    tags=["Tasks"], # Add a tag for grouping endpoints in OpenAPI UI
)


# --- Endpoints ---

@router.post(
    "/tasks/", # Note: prefix="/v1" is added in APIRouter
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a New Task",
    description="Accepts task details and submits it to the Ops-Core scheduler for asynchronous execution. Returns the initial state of the created task.",
    responses={
        status.HTTP_201_CREATED: {"description": "Task successfully submitted."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Invalid input data provided."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error during task submission."},
    },
)
async def create_task(
    task_request: TaskCreateRequest,
    scheduler: InMemoryScheduler = Depends(get_scheduler),
) -> Task:
    """
    Endpoint to submit a new task to the Ops-Core scheduler.

    - Receives task type and input data.
    - Generates a unique task ID (handled by the store/scheduler).
    - Submits the task to the configured scheduler via dependency injection.
    - Returns the newly created task object with its initial status (e.g., PENDING).
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
    "/tasks/{task_id}", # Note: prefix="/v1" is added in APIRouter
    response_model=TaskResponse,
    summary="Get Task Status and Details",
    description="Retrieves the complete details and current status of a specific task using its unique ID.",
    responses={
        status.HTTP_200_OK: {"description": "Task details successfully retrieved."},
        status.HTTP_404_NOT_FOUND: {"description": "Task with the specified ID was not found."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error during task retrieval."},
    },
)
async def get_task(
    task_id: str,
    metadata_store: InMemoryMetadataStore = Depends(get_metadata_store),
) -> Task:
    """
    Endpoint to retrieve a specific task by its unique ID.

    - Fetches task details from the metadata store.
    - Returns the complete task object if found.
    - Raises a 404 error if the task ID does not exist.
    """
    # Reason: Use the metadata store to fetch the task details.
    try:
        task = await metadata_store.get_task(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID '{task_id}' not found.",
            )
        return task
    except HTTPException:
        # Re-raise HTTPException (like 404) directly
        raise
    except Exception as e:
        # TODO: Add more specific error handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task: {e}",
        )


@router.get(
    "/tasks/", # Note: prefix="/v1" is added in APIRouter
    response_model=TaskListResponse,
    summary="List All Tasks",
    description="Retrieves a list of all tasks currently managed by the Ops-Core system. Future versions may include filtering and pagination.",
    responses={
        status.HTTP_200_OK: {"description": "List of tasks successfully retrieved."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error during task listing."},
    },
)
async def list_tasks(
    metadata_store: InMemoryMetadataStore = Depends(get_metadata_store),
    # TODO: Add pagination parameters (skip: int = 0, limit: int = 100)
) -> TaskListResponse:
    """
    Endpoint to retrieve a list of all tasks.

    - Fetches all tasks from the metadata store.
    - Returns a response containing the list of task objects and the total count.
    - (Pagination parameters `skip` and `limit` can be added later).
    """
    # Reason: Use the metadata store to get all tasks. Pagination should be added later.
    try:
        tasks = await metadata_store.list_tasks()
        return TaskListResponse(tasks=tasks, total=len(tasks))
    except Exception as e:
        # TODO: Add more specific error handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {e}",
        )
