"""
Models for Ops Core.

This package contains the Pydantic models used throughout the Ops Core system,
primarily for representing tasks, operations, and their metadata.
"""
from .tasks import Task, TaskStatus

__all__ = ["Task", "TaskStatus"]
