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

from dramatiq.brokers.stub import StubBroker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel # Import SQLModel

from ops_core.config.loader import get_resolved_mcp_config # Import config loader

from ops_core.config.loader import McpConfig # Import the type
from ops_core.metadata.store import InMemoryMetadataStore # Keep for other tests
from ops_core.mcp_client.client import OpsMcpClient
# Removed sys.path hack
from ops_core.scheduler.engine import execute_agent_task_actor # Import actor to get queue name

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

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Creates an async engine for the test session."""
    # statement_cache_size is incompatible with asyncpg
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """
    Provides a clean database state and an AsyncSession for each test function.
    Creates tables before the test and drops them afterwards.
    """
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    AsyncTestSessionLocal = sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncTestSessionLocal() as session:
        yield session
        # Optional: You might want additional cleanup logic here if needed

    # Drop tables after the test
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


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

@pytest.fixture(scope="function")
def stub_broker():
    """Provides a Dramatiq StubBroker."""
    broker = StubBroker()
    # Explicitly declare the queue used by the actor
    broker.declare_queue(execute_agent_task_actor.queue_name)
    # Middleware might be needed if tests rely on it, add here if necessary
    # broker.add_middleware(...)
    yield broker
    broker.flush_all() # Clear queues after test
