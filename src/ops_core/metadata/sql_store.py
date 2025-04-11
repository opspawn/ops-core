"""
SQL-based implementation of the metadata store using SQLModel.
"""

from typing import List, Optional, Any, Dict
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, SQLModel # Import SQLModel here

from ops_core.config.loader import get_resolved_mcp_config # Corrected import path
# Import current_utc_time as well
from ops_core.models.tasks import Task, TaskStatus, current_utc_time # Corrected import path
# Import directly from base where TaskNotFoundError is defined
from ops_core.metadata.base import BaseMetadataStore, TaskNotFoundError # Corrected import path

# Load database URL from config
config = get_resolved_mcp_config()
DATABASE_URL = config.database_url

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False) # Set echo=True for debugging SQL

# Create a sessionmaker for async sessions
AsyncSessionFactory = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Dependency to get an async session
@asynccontextmanager
async def get_session() -> AsyncSession:
    """Provide a transactional scope around a series of operations."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # Commit should happen *after* operations in the using block
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

class SqlMetadataStore(BaseMetadataStore):
    """
    SQLModel-based implementation of the metadata store for persisting task data.
    Can optionally be initialized with an existing session for testing.
    """
    def __init__(self, session: Optional[AsyncSession] = None):
        """
        Initializes the store.

        Args:
            session: An optional existing AsyncSession to use for operations.
                     If None, a new session will be created per operation using get_session().
        """
        self._session = session # Store the provided session if any

    @asynccontextmanager
    async def _get_session_context(self) -> AsyncSession:
        """Internal helper to get a session context."""
        if self._session:
            # If initialized with a session, use it directly without context management here
            # Assume the caller (e.g., test fixture) manages the session lifecycle
            yield self._session
        else:
            # Otherwise, use the global factory context manager
            async with get_session() as session:
                yield session

    async def add_task(self, task: Task) -> Task:
        """Adds a new task to the database."""
        async with self._get_session_context() as session: # Use helper context
            session.add(task)
            # Rely on the test fixture's transaction context manager to commit/rollback
            await session.flush() # Ensure the object gets an ID if needed before returning
            return task

    async def get_task(self, task_id: str) -> Task:
        """Retrieves a task by its ID."""
        async with self._get_session_context() as session: # Use helper context
            statement = select(Task).where(Task.task_id == task_id)
            result = await session.execute(statement)
            task = result.scalar_one_or_none()
            if task is None:
                raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
            # No commit needed for read operations
            return task

    async def update_task_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None) -> Task:
        """Updates the status of an existing task."""
        async with self._get_session_context() as session: # Use helper context
            # Fetch the task within the current session context
            statement = select(Task).where(Task.task_id == task_id)
            db_result = await session.execute(statement) # Rename query result variable
            task = db_result.scalar_one_or_none() # Use renamed variable
            if task is None:
                raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")

            # Use the model's helper method to update status and timestamps
            task.update_status(status, error_message) # Fix NameError: error_msg -> error_message
            session.add(task) # Add the modified task back to the session
            # Rely on the test fixture's transaction context manager to commit/rollback
            await session.flush() # Ensure changes are sent to DB before refresh
            await session.refresh(task) # Refresh to get updated state from DB
            return task

    async def update_task_output(self, task_id: str, result: Any) -> Task:
        """Updates the output data of a completed task."""
        async with self._get_session_context() as session: # Use helper context
            # Fetch the task within the current session context
            statement = select(Task).where(Task.task_id == task_id)
            db_result = await session.execute(statement) # Rename query result variable
            task = db_result.scalar_one_or_none() # Use renamed variable
            if task is None:
                raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")

            # Assign the input parameter 'result' (which is JSON serializable)
            task.result = result
            # Also update the 'updated_at' timestamp
            # Call the imported function directly
            task.updated_at = current_utc_time()
            session.add(task)
            # Rely on the test fixture's transaction context manager to commit/rollback
            await session.flush() # Ensure changes are sent to DB before returning
            # await session.refresh(task) # Refresh might not be needed if returning the same object
            return task

    async def list_tasks(self, limit: int = 100, offset: int = 0, status: Optional[TaskStatus] = None) -> List[Task]:
        """Lists tasks, optionally filtering by status."""
        async with self._get_session_context() as session: # Use helper context
            statement = select(Task).offset(offset).limit(limit).order_by(Task.created_at.desc())
            if status:
                statement = statement.where(Task.status == status)
            result = await session.execute(statement)
            tasks = result.scalars().all()
            # No commit needed for read operations
            return list(tasks)

# Helper function for potential initialization (e.g., creating tables)
async def init_db():
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all) # Use with caution!
        await conn.run_sync(SQLModel.metadata.create_all)

# Example of running init_db (e.g., in a startup script)
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(init_db())
#     print("Database initialized.")
