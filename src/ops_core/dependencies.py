"""
Dependency injection setup for the Ops-Core application.

Provides instances of shared resources like database sessions, metadata stores,
and MCP clients.
"""
import os
from typing import Optional, AsyncGenerator, TYPE_CHECKING
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv
from fastapi import Depends

from ops_core.metadata.base import BaseMetadataStore # Corrected import path
from ops_core.metadata.sql_store import SqlMetadataStore # Corrected import path
# Keep InMemoryStore for potential fallback or specific tests if needed later
# from ops_core.metadata.store import InMemoryMetadataStore # Corrected path (if needed)
# Defer scheduler import to break cycle
# from ops_core.scheduler.engine import InMemoryScheduler
from ops_core.mcp_client.client import OpsMcpClient # Corrected import path

# Use TYPE_CHECKING for type hints involving circular dependencies
if TYPE_CHECKING:
    from ops_core.scheduler.engine import InMemoryScheduler # Corrected import path

# --- Database Setup ---
load_dotenv() # Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")

# Configure the async engine
# echo=True can be useful for debugging SQL statements
async_engine = create_async_engine(DATABASE_URL, echo=False)

# Configure the session factory
# expire_on_commit=False prevents attributes from being expired after commit.
async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injector that provides a SQLAlchemy AsyncSession.

    Ensures the session is automatically closed after the request.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

# --- MCP Client Dependency ---
# Define MCP client dependencies *before* other functions that might use them

class AppDependencies:
    """Holds shared application dependency instances (primarily for singleton-like patterns)."""
    # metadata_store is now session-scoped, removed from here.
    mcp_client: Optional[OpsMcpClient] = None

# Global instance of the container (mainly for MCP client now)
deps = AppDependencies()

# TODO: Consider initializing MCP client during app lifespan startup
#       instead of lazy initialization here for better error handling at startup.
def get_mcp_client() -> OpsMcpClient:
    """Dependency injector function for MCP client."""
    if deps.mcp_client is None:
        # Similar fallback/warning as above
        print("Warning: Initializing OpsMcpClient directly in get_mcp_client.")
        deps.mcp_client = OpsMcpClient()
        # In a real scenario, you might want async startup here too
        # await deps.mcp_client.start_all_servers()
    return deps.mcp_client

# --- Metadata Store Dependency ---

async def get_metadata_store(
    session: AsyncSession = Depends(get_db_session) # Inject the session
) -> BaseMetadataStore:
    """
    Dependency injector function for the metadata store.

    Provides an instance of SqlMetadataStore initialized with the request-scoped session.
    """
    # Pass the injected session to the store constructor
    return SqlMetadataStore(session=session)

# --- Scheduler Dependency ---

# TODO: Consider making the scheduler a singleton similar to MCP client if appropriate
#       Currently, a new instance is created per request needing it.
async def get_scheduler(
    metadata_store: BaseMetadataStore = Depends(get_metadata_store),
    mcp_client: OpsMcpClient = Depends(get_mcp_client)
) -> "InMemoryScheduler": # Use string type hint
    """
    Dependency injector function for the scheduler.

    Provides an instance of InMemoryScheduler initialized with dependencies.
    """
    # Import locally to break the circular dependency at import time
    from ops_core.scheduler.engine import InMemoryScheduler # Corrected import path
    # Note: InMemoryScheduler might need adjustments if its __init__ signature changed
    return InMemoryScheduler(metadata_store=metadata_store, mcp_client=mcp_client)
