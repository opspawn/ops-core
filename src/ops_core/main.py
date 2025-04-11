"""
Main FastAPI application entry point for Ops-Core.
"""
import contextlib
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Import the tasks router
from ops_core.api.v1.endpoints import tasks as tasks_v1
# Import dependencies container and initializers
from ops_core.dependencies import deps, get_metadata_store, get_mcp_client
from ops_core.metadata.store import InMemoryMetadataStore
from ops_core.mcp_client.client import OpsMcpClient


@asynccontextmanager
async def initialize_dependencies(app: FastAPI):
    """FastAPI lifespan context manager to initialize dependencies."""
    print("Initializing dependencies...")
    deps.metadata_store = InMemoryMetadataStore()
    deps.mcp_client = OpsMcpClient()
    try:
        await deps.mcp_client.start_all_servers()
        print("Dependencies initialized.")
        yield # Application runs here
    finally:
        print("Shutting down dependencies...")
        if deps.mcp_client:
            await deps.mcp_client.stop_all_servers()
        print("Dependencies shut down.")


app = FastAPI(
    title="Ops-Core API",
    description="API for managing Opspawn tasks and agents.",
    version="0.1.0",
    lifespan=initialize_dependencies # Register the lifespan context manager
)

# Include the v1 tasks router
# Note: The router's dependency overrides will now use the functions
# from dependencies.py which access the initialized 'deps' container.
app.include_router(tasks_v1.router, prefix="/api/v1", tags=["tasks"])


# Health check can remain if desired, or be removed.
@app.get("/health", tags=["health"])
async def health_check():
    """
    Simple health check endpoint.
    """
    # Optionally check if dependencies are initialized
    store_ok = deps.metadata_store is not None
    client_ok = deps.mcp_client is not None
    return {"status": "ok", "metadata_store_initialized": store_ok, "mcp_client_initialized": client_ok}

# Add other global configurations or middleware if needed
