"""
Global pytest fixtures and configuration for ops_core tests.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from dramatiq.brokers.stub import StubBroker

from ops_core.config.loader import McpConfig # Import the type
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient
from ops_core.scheduler.engine import execute_agent_task_actor # Import actor to get queue name


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
    """Provides a Dramatiq StubBroker with the actor's queue declared."""
    broker = StubBroker()
    # Explicitly declare the queue used by the actor
    broker.declare_queue(execute_agent_task_actor.queue_name)
    # Middleware might be needed if tests rely on it, add here if necessary
    # broker.add_middleware(...)
    yield broker
    broker.flush_all() # Clear queues after test
