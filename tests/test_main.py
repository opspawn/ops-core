"""
Unit tests for the main FastAPI application setup in ops_core.main.
"""

from fastapi.testclient import TestClient
from ops_core.main import app # Import the FastAPI app instance
from ops_core.api.v1.endpoints import tasks as tasks_api # Import the router


def test_app_includes_task_router():
    """Verify that the main app includes the tasks API router."""
    # Check if the router from tasks_api is included in the app's routers
    # Note: FastAPI stores routes, not routers directly in app.routes after inclusion
    # We need to check for the *prefixed* routes in the main app.
    api_prefix = "/api/v1" # As defined in main.py app.include_router
    expected_prefixed_routes = {api_prefix + route.path for route in tasks_api.router.routes}
    app_routes = {route.path for route in app.routes}

    # Check if all expected prefixed routes from the task router are present in the main app routes
    assert expected_prefixed_routes.issubset(app_routes), \
        f"Not all task routes found in app with prefix '{api_prefix}'. Missing: {expected_prefixed_routes - app_routes}"

    # Optional: Test a specific known route from the tasks router via TestClient
    client = TestClient(app)
    # Example: Check if the GET /api/v1/tasks/ endpoint exists (even if it needs overrides to function)
    # We expect a 422 if no query params are given, or potentially another error
    # if dependencies aren't overridden, but a 404 would mean the route isn't registered.
    response = client.get("/api/v1/tasks/")
    assert response.status_code != 404, "GET /api/v1/tasks/ route not found in app."
