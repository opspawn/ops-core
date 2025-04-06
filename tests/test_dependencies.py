"""
Unit tests for the dependency getter functions in ops_core.dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock

# Import the functions to test
from ops_core.dependencies import (
    get_metadata_store,
    # get_scheduler, # This function does not exist in dependencies.py
    get_mcp_client,
    # Do not import internal implementation details like _metadata_store_instance
)
# Import the module itself to modify its globals in the fixture
import ops_core.dependencies

# Import the classes these functions are supposed to return instances of
from ops_core.metadata.store import InMemoryMetadataStore
# from ops_core.scheduler.engine import InMemoryScheduler # Not needed for these tests
from ops_core.mcp_client.client import OpsMcpClient


@pytest.fixture(autouse=True)
def reset_singletons():
    """Fixture to reset singleton instances before each test."""
    # Reset the instances directly within the dependencies module's container
    ops_core.dependencies.deps.metadata_store = None
    ops_core.dependencies.deps.mcp_client = None
    yield
    # Reset again after test
    ops_core.dependencies.deps.metadata_store = None
    ops_core.dependencies.deps.mcp_client = None


def test_get_metadata_store_returns_instance():
    """Verify get_metadata_store returns an instance of InMemoryMetadataStore."""
    store = get_metadata_store()
    assert isinstance(store, InMemoryMetadataStore)


def test_get_metadata_store_is_singleton():
    """Verify get_metadata_store returns the same instance on subsequent calls."""
    store1 = get_metadata_store()
    store2 = get_metadata_store()
    assert store1 is store2


# Removed tests for get_scheduler as the function does not exist


def test_get_mcp_client_returns_instance():
    """Verify get_mcp_client returns an instance of OpsMcpClient."""
    # Mock the config loader to return an object with a 'servers' attribute
    mock_config = MagicMock()
    mock_config.servers = [] # Mock the expected attribute
    with patch('ops_core.mcp_client.client.get_resolved_mcp_config', return_value=mock_config):
        client = get_mcp_client()
        assert isinstance(client, OpsMcpClient)


def test_get_mcp_client_is_singleton():
    """Verify get_mcp_client returns the same instance on subsequent calls."""
    # Mock the config loader to return an object with a 'servers' attribute
    mock_config = MagicMock()
    mock_config.servers = [] # Mock the expected attribute
    with patch('ops_core.mcp_client.client.get_resolved_mcp_config', return_value=mock_config) as mock_get_config:
        client1 = get_mcp_client()
        # Ensure the config loader isn't called again on the second call
        mock_get_config.reset_mock() # Reset mock call count
        client2 = get_mcp_client()
        assert client1 is client2
        mock_get_config.assert_not_called()
