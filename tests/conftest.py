"""
Global pytest fixtures and configuration for ops_core tests.
"""

import pytest
import pytest_asyncio
import pytest
import pytest_asyncio
import asyncio
import os # Added
from dotenv import load_dotenv # Added
from unittest.mock import patch, MagicMock, AsyncMock
import dramatiq # Import dramatiq
from dramatiq.brokers.stub import StubBroker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete # Added import
# Import SQLModel is no longer needed here if we use the specific metadata
# from sqlmodel import SQLModel

# Import the shared metadata object and specific models needed for clearing
from ops_core.models.base import metadata
# Removed Task import - it should be implicitly known by metadata
# from ops_core.models.tasks import Task # Added import

from ops_core.config.loader import get_resolved_mcp_config # Import config loader

from ops_core.config.loader import McpConfig # Import the type
from ops_core.metadata.store import InMemoryMetadataStore # Corrected path, keep for other tests
from ops_core.mcp_client.client import OpsMcpClient # Corrected path
# Removed sys.path hack
# Removed actor import to break collection-time dependency chain causing metadata error
# from src.ops_core.scheduler.engine import execute_agent_task_actor

# Load environment variables from .env file in the project root
# This ensures DATABASE_URL is available for tests
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)


# --- Database Fixtures for SqlMetadataStore Tests ---

# Use a separate test database URL if possible, or ensure clean state
# For simplicity here, we'll use the default but manage tables.
# In a real scenario, use a dedicated test DB URL via env var.
# TEST_DATABASE_URL = get_resolved_mcp_config().database_url # Original attempt
TEST_DATABASE_URL = os.getenv("DATABASE_URL") # Directly get from loaded env
if not TEST_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set or .env file not found.")

# Modify URL slightly if needed for testing (e.g., different DB name)
# TEST_DATABASE_URL = TEST_DATABASE_URL.replace("/opspawn_db", "/test_opspawn_db")

# Removed deprecated custom event_loop fixture; rely on pytest-asyncio default

# Function-scoped engine, created once per test function run
@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Provides an async engine fixture, managing tables for a single test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Ensure clean start and create tables using shared metadata
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    yield engine
    # Dispose the engine after all tests in the module are done
    await engine.dispose()

# Function-scoped session, ensures test isolation via transactions
@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """
    Provides a transactional AsyncSession for each test function.
    Changes are rolled back automatically after each test.
    Also explicitly clears the Task table before yielding.
    """
    async_session_factory = sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        # Explicitly delete all tasks before starting the test transaction
        # This is an extra safety measure against state leakage
        # Need to re-import Task locally for delete() to work
        from ops_core.models.tasks import Task
        await session.execute(delete(Task))
        await session.commit() # Commit the delete before yielding

        # Yield the session directly without transaction management here
        yield session
        # Rely on db_engine drop/create for isolation between tests
        await session.close()


# --- Existing Fixtures ---

@pytest_asyncio.fixture(scope="function")
async def mock_metadata_store() -> InMemoryMetadataStore:
    """Provides a clean InMemoryMetadataStore for each test function."""
    return InMemoryMetadataStore()

# Rename fixture to avoid conflict if used directly in tests needing the other one
@pytest_asyncio.fixture(scope="function")
async def mock_mcp_client() -> MagicMock:
    """Provides a mocked OpsMcpClient for each test function."""
    client = MagicMock(spec=OpsMcpClient)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()
    client.call_tool = AsyncMock()
    # Add other methods if needed by tests
    return client

# Removed stub_broker fixture definition. Broker setup will be handled explicitly where needed.

# --- Global Test Setup ---

# Removed pytest_configure hook as broker setup is now handled conditionally
# in src/ops_core/tasks/broker.py based on DRAMATIQ_TESTING env var.

# Removed autouse set_stub_broker fixture.
