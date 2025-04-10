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
# Import SQLModel is no longer needed here if we use the specific metadata
# from sqlmodel import SQLModel

# Import the shared metadata object
from src.ops_core.models.base import metadata

from ops_core.config.loader import get_resolved_mcp_config # Import config loader

from ops_core.config.loader import McpConfig # Import the type
from src.ops_core.metadata.store import InMemoryMetadataStore # Corrected path, keep for other tests
from src.ops_core.mcp_client.client import OpsMcpClient # Corrected path
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

# Removed session-scoped db_engine fixture

# Removed session-scoped _setup_database fixture

@pytest_asyncio.fixture(scope="function")
async def db_session(): # Now function-scoped, creates engine and tables
    """
    Provides an AsyncSession for each test function with a clean database state.
    Creates a new engine and tables for each test and drops them afterwards.
    """
    # Create engine within the function scope
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables using the shared metadata object
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    # Create session factory bound to this engine
    AsyncTestSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncTestSessionLocal() as session:
        yield session # Provide the session to the test

    # Drop tables using the shared metadata object after the test
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)

    # Dispose the engine
    await engine.dispose()


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
