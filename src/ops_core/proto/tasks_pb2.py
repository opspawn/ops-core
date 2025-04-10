# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: tasks.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import struct_pb2 as google_dot_protobuf_dot_struct__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0btasks.proto\x12\x0eops_core.proto\x1a\x1cgoogle/protobuf/struct.proto\x1a\x1fgoogle/protobuf/timestamp.proto\"\x8a\x03\n\x04Task\x12\x0f\n\x07task_id\x18\x01 \x01(\t\x12\x11\n\ttask_type\x18\x02 \x01(\t\x12*\n\x06status\x18\x03 \x01(\x0e\x32\x1a.ops_core.proto.TaskStatus\x12+\n\ninput_data\x18\x04 \x01(\x0b\x32\x17.google.protobuf.Struct\x12,\n\x0boutput_data\x18\x05 \x01(\x0b\x32\x17.google.protobuf.Struct\x12.\n\ncreated_at\x18\x06 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12.\n\nupdated_at\x18\x07 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12.\n\nstarted_at\x18\x08 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x30\n\x0c\x63ompleted_at\x18\t \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x15\n\rerror_message\x18\n \x01(\t\"S\n\x11\x43reateTaskRequest\x12\x11\n\ttask_type\x18\x01 \x01(\t\x12+\n\ninput_data\x18\x02 \x01(\x0b\x32\x17.google.protobuf.Struct\"8\n\x12\x43reateTaskResponse\x12\"\n\x04task\x18\x01 \x01(\x0b\x32\x14.ops_core.proto.Task\"!\n\x0eGetTaskRequest\x12\x0f\n\x07task_id\x18\x01 \x01(\t\"5\n\x0fGetTaskResponse\x12\"\n\x04task\x18\x01 \x01(\x0b\x32\x14.ops_core.proto.Task\"\x12\n\x10ListTasksRequest\"G\n\x11ListTasksResponse\x12#\n\x05tasks\x18\x01 \x03(\x0b\x32\x14.ops_core.proto.Task\x12\r\n\x05total\x18\x03 \x01(\x05*m\n\nTaskStatus\x12\x1b\n\x17TASK_STATUS_UNSPECIFIED\x10\x00\x12\x0b\n\x07PENDING\x10\x01\x12\x0b\n\x07RUNNING\x10\x02\x12\r\n\tCOMPLETED\x10\x03\x12\n\n\x06\x46\x41ILED\x10\x04\x12\r\n\tCANCELLED\x10\x05\x32\x80\x02\n\x0bTaskService\x12S\n\nCreateTask\x12!.ops_core.proto.CreateTaskRequest\x1a\".ops_core.proto.CreateTaskResponse\x12J\n\x07GetTask\x12\x1e.ops_core.proto.GetTaskRequest\x1a\x1f.ops_core.proto.GetTaskResponse\x12P\n\tListTasks\x12 .ops_core.proto.ListTasksRequest\x1a!.ops_core.proto.ListTasksResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'tasks_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_TASKSTATUS']._serialized_start=817
  _globals['_TASKSTATUS']._serialized_end=926
  _globals['_TASK']._serialized_start=95
  _globals['_TASK']._serialized_end=489
  _globals['_CREATETASKREQUEST']._serialized_start=491
  _globals['_CREATETASKREQUEST']._serialized_end=574
  _globals['_CREATETASKRESPONSE']._serialized_start=576
  _globals['_CREATETASKRESPONSE']._serialized_end=632
  _globals['_GETTASKREQUEST']._serialized_start=634
  _globals['_GETTASKREQUEST']._serialized_end=667
  _globals['_GETTASKRESPONSE']._serialized_start=669
  _globals['_GETTASKRESPONSE']._serialized_end=722
  _globals['_LISTTASKSREQUEST']._serialized_start=724
  _globals['_LISTTASKSREQUEST']._serialized_end=742
  _globals['_LISTTASKSRESPONSE']._serialized_start=744
  _globals['_LISTTASKSRESPONSE']._serialized_end=815
  _globals['_TASKSERVICE']._serialized_start=929
  _globals['_TASKSERVICE']._serialized_end=1185
# @@protoc_insertion_point(module_scope)
