"""
Simple dependency container for shared application instances.
"""

from typing import Optional
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient

class AppDependencies:
    """Holds shared application dependency instances."""
    metadata_store: Optional[InMemoryMetadataStore] = None
    mcp_client: Optional[OpsMcpClient] = None

# Global instance of the container
deps = AppDependencies()

def get_metadata_store() -> InMemoryMetadataStore:
    """Dependency injector function for metadata store."""
    if deps.metadata_store is None:
        # This path should ideally not be hit in production if lifespan initializes correctly
        # but provides a fallback for simpler scenarios or tests if needed.
        # Consider raising an error here in strict production setups.
        print("Warning: Initializing InMemoryMetadataStore directly in get_metadata_store.")
        deps.metadata_store = InMemoryMetadataStore()
    return deps.metadata_store

def get_mcp_client() -> OpsMcpClient:
    """Dependency injector function for MCP client."""
    if deps.mcp_client is None:
        # Similar fallback/warning as above
        print("Warning: Initializing OpsMcpClient directly in get_mcp_client.")
        deps.mcp_client = OpsMcpClient()
        # In a real scenario, you might want async startup here too
        # await deps.mcp_client.start_all_servers()
    return deps.mcp_client
