"""
gRPC Servicer implementation for the TaskService.
"""

# Explicitly import required submodules instead of top-level grpc
from grpc import aio as grpc_aio
from grpc import StatusCode
import logging
from google.protobuf import timestamp_pb2, struct_pb2
from typing import Dict, Any

# Import generated gRPC code and protobuf messages (now relative imports)
from . import tasks_pb2
from . import tasks_pb2_grpc

# Import core components
from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.models import Task as CoreTask, TaskStatus as CoreTaskStatus

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _core_task_status_to_proto(status: CoreTaskStatus) -> tasks_pb2.TaskStatus:
    """Converts core TaskStatus enum to protobuf TaskStatus enum."""
    status_map = {
        CoreTaskStatus.PENDING: tasks_pb2.PENDING,
        CoreTaskStatus.RUNNING: tasks_pb2.RUNNING,
        CoreTaskStatus.COMPLETED: tasks_pb2.COMPLETED,
        CoreTaskStatus.FAILED: tasks_pb2.FAILED,
        CoreTaskStatus.CANCELLED: tasks_pb2.CANCELLED,
    }
    return status_map.get(status, tasks_pb2.TASK_STATUS_UNSPECIFIED)

def _dict_to_struct(data: Dict[str, Any]) -> struct_pb2.Struct:
    """Converts a Python dictionary to a protobuf Struct."""
    s = struct_pb2.Struct()
    s.update(data)
    return s

def _core_task_to_proto(core_task: CoreTask) -> tasks_pb2.Task:
    """Converts a core Task model to a protobuf Task message."""
    proto_task = tasks_pb2.Task(
        task_id=core_task.task_id,
        task_type=core_task.task_type,
        status=_core_task_status_to_proto(core_task.status),
        input_data=_dict_to_struct(core_task.input_data or {}),
        output_data=_dict_to_struct(core_task.output_data or {}),
        error_message=core_task.error_message or "",
    )
    # Convert datetimes to Timestamps
    if core_task.created_at:
        proto_task.created_at.FromDatetime(core_task.created_at)
    if core_task.updated_at:
        proto_task.updated_at.FromDatetime(core_task.updated_at)
    if core_task.started_at:
        proto_task.started_at.FromDatetime(core_task.started_at)
    if core_task.completed_at:
        proto_task.completed_at.FromDatetime(core_task.completed_at)
    return proto_task


# --- Servicer Implementation ---

class TaskServicer(tasks_pb2_grpc.TaskServiceServicer):
    """
    Implements the TaskService gRPC interface.
    """

    def __init__(self, scheduler: InMemoryScheduler):
        """
        Initializes the servicer with dependencies.

        Args:
            scheduler: The scheduler instance.
        """
        self._scheduler = scheduler
        self._metadata_store = scheduler._metadata_store # Correctly access private attribute
        logger.info("TaskServicer initialized.")

    async def CreateTask(
        self, request: tasks_pb2.CreateTaskRequest, context: grpc_aio.ServicerContext # Use imported aio
    ) -> tasks_pb2.CreateTaskResponse:
        """
        Handles the CreateTask RPC call.
        """
        logger.info(f"gRPC CreateTask called for type: {request.task_type}")
        try:
            # Convert Struct to dict for core scheduler
            input_data_dict = dict(request.input_data.items())
            # Generate a default name
            task_name = f"gRPC Task - {request.task_type}"
            core_task = await self._scheduler.submit_task(
                name=task_name, # Pass the generated name
                task_type=request.task_type,
                input_data=input_data_dict,
            )
            proto_task = _core_task_to_proto(core_task)
            return tasks_pb2.CreateTaskResponse(task=proto_task)
        except Exception as e:
            logger.error(f"Error creating task via gRPC: {e}", exc_info=True)
            # Use imported StatusCode
            await context.abort(StatusCode.INTERNAL, f"Failed to create task: {e}")

    async def GetTask(
        self, request: tasks_pb2.GetTaskRequest, context: grpc_aio.ServicerContext # Use imported aio
    ) -> tasks_pb2.GetTaskResponse:
        """
        Handles the GetTask RPC call.
        """
        logger.info(f"gRPC GetTask called for ID: {request.task_id}")
        core_task = await self._metadata_store.get_task(request.task_id)
        if core_task is None:
            logger.warning(f"Task not found via gRPC: {request.task_id}")
            # Use imported StatusCode
            await context.abort(StatusCode.NOT_FOUND, f"Task with ID '{request.task_id}' not found.")
        else:
            proto_task = _core_task_to_proto(core_task)
            return tasks_pb2.GetTaskResponse(task=proto_task)

    async def ListTasks(
        self, request: tasks_pb2.ListTasksRequest, context: grpc_aio.ServicerContext # Use imported aio
    ) -> tasks_pb2.ListTasksResponse:
        """
        Handles the ListTasks RPC call.
        """
        logger.info("gRPC ListTasks called")
        # TODO: Add filtering based on request if implemented later
        core_tasks = await self._metadata_store.list_tasks()
        proto_tasks = [_core_task_to_proto(task) for task in core_tasks]
        return tasks_pb2.ListTasksResponse(tasks=proto_tasks, total=len(proto_tasks))
