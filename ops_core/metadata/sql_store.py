"""
SQL-based implementation of the metadata store using SQLModel.
"""

from typing import List, Optional, Any, Dict
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, SQLModel # Import SQLModel here

from ops_core.config.loader import get_resolved_mcp_config
from ops_core.models.tasks import Task, TaskStatus
from ops_core.metadata.store import BaseMetadataStore, TaskNotFoundError

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
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

class SqlMetadataStore(BaseMetadataStore):
    """
    SQLModel-based implementation of the metadata store for persisting task data.
    """

    async def add_task(self, task: Task) -> Task:
        """Adds a new task to the database."""
        async with get_session() as session:
            session.add(task)
            # No need to commit here, context manager handles it
            # Removed session.refresh(task) as it's not needed for adding new objects
            # with client-generated PKs and causes errors.
            # The task object added to the session will be returned implicitly
            # after the context manager commits. We return the original task object.
            return task

    async def get_task(self, task_id: str) -> Task:
        """Retrieves a task by its ID."""
        async with get_session() as session:
            statement = select(Task).where(Task.task_id == task_id)
            result = await session.execute(statement)
            task = result.scalar_one_or_none()
            if task is None:
                raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
            return task

    async def update_task_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None) -> Task:
        """Updates the status of an existing task."""
        async with get_session() as session:
            task = await self.get_task(task_id) # Reuse get_task for existence check
            # Use the model's helper method to update status and timestamps
            task.update_status(status, error_msg)
            session.add(task) # Add the modified task back to the session
            await session.flush() # Ensure changes are sent to DB before refresh
            await session.refresh(task)
            return task

    async def update_task_output(self, task_id: str, result: Any) -> Task:
        """Updates the output data of a completed task."""
        async with get_session() as session:
            task = await self.get_task(task_id) # Reuse get_task for existence check
            task.result = result
            # Also update the 'updated_at' timestamp
            task.updated_at = task.current_utc_time() # Assuming current_utc_time is available or imported
            session.add(task)
            await session.flush()
            await session.refresh(task)
            return task

    async def list_tasks(self, limit: int = 100, offset: int = 0, status: Optional[TaskStatus] = None) -> List[Task]:
        """Lists tasks, optionally filtering by status."""
        async with get_session() as session:
            statement = select(Task).offset(offset).limit(limit).order_by(Task.created_at.desc())
            if status:
                statement = statement.where(Task.status == status)
            result = await session.execute(statement)
            tasks = result.scalars().all()
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
