"""
Custom Exceptions for the Ops-Core Module.
"""

class OpsCoreError(Exception):
    """Base class for exceptions in this module."""
    pass

class AgentNotFoundError(OpsCoreError):
    """Raised when an agent ID is not found in storage."""
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")

class SessionNotFoundError(OpsCoreError):
    """Raised when a session ID is not found in storage."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")

class WorkflowDefinitionNotFoundError(OpsCoreError):
    """Raised when a workflow definition ID is not found."""
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        super().__init__(f"Workflow definition not found: {workflow_id}")

class InvalidStateError(OpsCoreError):
    """Raised when an invalid state transition or value is encountered."""
    def __init__(self, message: str):
        super().__init__(message)

class StorageError(OpsCoreError):
    """Raised for general storage-related errors."""
    def __init__(self, message: str, original_exception: Exception = None):
        self.original_exception = original_exception
        super().__init__(f"Storage error: {message}")

class RegistrationError(OpsCoreError):
    """Raised for errors during agent registration."""
    def __init__(self, message: str, original_exception: Exception = None):
        self.original_exception = original_exception
        super().__init__(f"Registration error: {message}")

class WorkflowDefinitionError(OpsCoreError):
    """Raised for errors related to workflow definition loading or validation."""
    def __init__(self, message: str, original_exception: Exception = None):
        self.original_exception = original_exception
        super().__init__(f"Workflow definition error: {message}")

class TaskDispatchError(OpsCoreError):
    """Raised for errors during task dispatching."""
    def __init__(self, agent_id: str, task_id: str, message: str, original_exception: Exception = None):
        self.agent_id = agent_id
        self.task_id = task_id
        self.original_exception = original_exception
        super().__init__(f"Task dispatch error for task '{task_id}' to agent '{agent_id}': {message}")

class ConfigurationError(OpsCoreError):
    """Raised for configuration-related errors."""
    pass
class AgentAlreadyExistsError(RegistrationError):
    """Raised when attempting to register an agent that already exists."""
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} already exists.")
from starlette import status # Import status codes

def get_status_code_for_exception(exc: OpsCoreError) -> int:
    """
    Maps OpsCoreError subclasses to appropriate HTTP status codes.

    Args:
        exc: An instance of OpsCoreError or its subclass.

    Returns:
        The corresponding HTTP status code.
    """
    if isinstance(exc, (AgentNotFoundError, SessionNotFoundError, WorkflowDefinitionNotFoundError)):
        return status.HTTP_404_NOT_FOUND
    elif isinstance(exc, AgentAlreadyExistsError):
        return status.HTTP_409_CONFLICT
    elif isinstance(exc, (InvalidStateError, RegistrationError, WorkflowDefinitionError)):
        # Treat general registration/definition errors and invalid states as bad requests
        return status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, (StorageError, TaskDispatchError, ConfigurationError)):
        # Treat storage, dispatch, and config errors as internal server errors
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        # Default for base OpsCoreError or any unmapped subclass
        return status.HTTP_500_INTERNAL_SERVER_ERROR