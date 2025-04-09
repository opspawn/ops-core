"""
Dependency injection setup for the Ops-Core application.

Provides instances of shared resources like database sessions, metadata stores,
and MCP clients.
"""
import os
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv
from fastapi import Depends

from ops_core.metadata.base import BaseMetadataStore
from ops_core.metadata.sql_store import SqlMetadataStore
# Keep InMemoryStore for potential fallback or specific tests if needed later
# from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient

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

# --- Metadata Store Dependency ---

async def get_metadata_store(
    session: AsyncSession = Depends(get_db_session) # Inject DB session
) -> BaseMetadataStore:
    """
    Dependency injector function for the metadata store.

    Provides an instance of SqlMetadataStore initialized with a database session.
    """
    return SqlMetadataStore(session)

# --- MCP Client Dependency ---

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
