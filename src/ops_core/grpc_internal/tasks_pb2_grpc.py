# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from . import tasks_pb2 as tasks__pb2


class TaskServiceStub(object):
    """Defines the gRPC service for managing tasks within the Ops-Core system.
    Provides methods for creating, retrieving, and listing tasks.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.CreateTask = channel.unary_unary(
                '/ops_core.proto.TaskService/CreateTask',
                request_serializer=tasks__pb2.CreateTaskRequest.SerializeToString,
                response_deserializer=tasks__pb2.CreateTaskResponse.FromString,
                )
        self.GetTask = channel.unary_unary(
                '/ops_core.proto.TaskService/GetTask',
                request_serializer=tasks__pb2.GetTaskRequest.SerializeToString,
                response_deserializer=tasks__pb2.GetTaskResponse.FromString,
                )
        self.ListTasks = channel.unary_unary(
                '/ops_core.proto.TaskService/ListTasks',
                request_serializer=tasks__pb2.ListTasksRequest.SerializeToString,
                response_deserializer=tasks__pb2.ListTasksResponse.FromString,
                )


class TaskServiceServicer(object):
    """Defines the gRPC service for managing tasks within the Ops-Core system.
    Provides methods for creating, retrieving, and listing tasks.
    """

    def CreateTask(self, request, context):
        """Submits a new task to the Ops-Core scheduler for asynchronous execution.
        Returns the initial state of the created task.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetTask(self, request, context):
        """Retrieves the complete details and current status of a specific task using its unique ID.
        Returns the task details or an error if not found.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ListTasks(self, request, context):
        """Retrieves a list of tasks managed by the Ops-Core system.
        Future versions may support filtering and pagination.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_TaskServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'CreateTask': grpc.unary_unary_rpc_method_handler(
                    servicer.CreateTask,
                    request_deserializer=tasks__pb2.CreateTaskRequest.FromString,
                    response_serializer=tasks__pb2.CreateTaskResponse.SerializeToString,
            ),
            'GetTask': grpc.unary_unary_rpc_method_handler(
                    servicer.GetTask,
                    request_deserializer=tasks__pb2.GetTaskRequest.FromString,
                    response_serializer=tasks__pb2.GetTaskResponse.SerializeToString,
            ),
            'ListTasks': grpc.unary_unary_rpc_method_handler(
                    servicer.ListTasks,
                    request_deserializer=tasks__pb2.ListTasksRequest.FromString,
                    response_serializer=tasks__pb2.ListTasksResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'ops_core.proto.TaskService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class TaskService(object):
    """Defines the gRPC service for managing tasks within the Ops-Core system.
    Provides methods for creating, retrieving, and listing tasks.
    """

    @staticmethod
    def CreateTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/ops_core.proto.TaskService/CreateTask',
            tasks__pb2.CreateTaskRequest.SerializeToString,
            tasks__pb2.CreateTaskResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetTask(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/ops_core.proto.TaskService/GetTask',
            tasks__pb2.GetTaskRequest.SerializeToString,
            tasks__pb2.GetTaskResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ListTasks(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/ops_core.proto.TaskService/ListTasks',
            tasks__pb2.ListTasksRequest.SerializeToString,
            tasks__pb2.ListTasksResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
