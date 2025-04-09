#!/bin/bash
# Script to fix imports in generated gRPC code (now in grpc/ dir)

set -e # Exit immediately if a command exits with a non-zero status.

# Get the target directory from the first argument passed by tox
TARGET_DIR="$1"

if [ -z "$TARGET_DIR" ]; then
  echo "Error: Target directory argument not provided."
  exit 1
fi

# Define target file path based on the argument
GRPC_FILE="${TARGET_DIR}/tasks_pb2_grpc.py"

# Ensure the target file exists
if [ ! -f "$GRPC_FILE" ]; then
  echo "Error: ${GRPC_FILE} not found."
  exit 1
fi

echo "Fixing import in ${GRPC_FILE} to be relative..."
# Use a temporary file for sed compatibility across versions
# Change 'import tasks_pb2' to 'from . import tasks_pb2'
sed 's/^import tasks_pb2 as tasks__pb2/from . import tasks_pb2 as tasks__pb2/' "${GRPC_FILE}" > "${GRPC_FILE}.tmp" && mv "${GRPC_FILE}.tmp" "${GRPC_FILE}"

echo "Finished fixing import in ${GRPC_FILE}."
