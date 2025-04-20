# tests/test_middleware.py
"""
Tests for the custom FastAPI middleware in opscore.middleware.
"""

import pytest
import pytest_asyncio # Import for async fixture
import logging
import json # Import json for log parsing
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from httpx import AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Assume opscore is importable (adjust path if needed, e.g., via conftest.py)
from opscore.middleware import RequestLoggingMiddleware, ErrorHandlerMiddleware
from opscore.exceptions import AgentNotFoundError, InvalidStateError, OpsCoreError, get_status_code_for_exception

# --- Test Fixtures ---

@pytest.fixture
def test_app():
    """Fixture to create a FastAPI app instance with middleware for testing."""
    app = FastAPI()

    # Add a dummy route that can succeed or raise errors
    @app.get("/test/success")
    async def route_success():
        return PlainTextResponse("Success")

    @app.get("/test/agent_not_found")
    async def route_agent_not_found():
        raise AgentNotFoundError("test-agent-id")

    @app.get("/test/invalid_state")
    async def route_invalid_state():
        raise InvalidStateError("Invalid state provided")

    @app.get("/test/generic_exception")
    async def route_generic_exception():
        raise ValueError("Something unexpected went wrong")

    @app.get("/test/http_exception")
    async def route_http_exception():
        raise HTTPException(status_code=status.HTTP_418_IM_A_TEAPOT, detail="I'm a teapot")

    # Add middleware in the standard order: Logging first, then Error Handling
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    return app

@pytest_asyncio.fixture # Use pytest_asyncio decorator
async def local_middleware_client(test_app): # Rename fixture
    """Fixture to create an httpx AsyncClient for the local middleware test app."""
    # Use async with for proper client lifecycle management
    async with AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client # Yield the client to the test

# --- Test Cases ---

@pytest.mark.asyncio
async def test_request_logging_middleware_success(local_middleware_client, caplog): # Use renamed fixture
    """Verify logs for a successful request."""
    caplog.set_level(logging.INFO) # Ensure INFO level logs are captured

    response = await local_middleware_client.get("/test/success") # Use renamed fixture

    assert response.status_code == 200
    assert response.text == "Success"
    assert "X-Process-Time" in response.headers # Check if header is added

    # Check log records
    log_records = [rec for rec in caplog.records if rec.name == 'opscore.middleware']
    assert len(log_records) >= 2 # Expect at least one incoming and one outgoing log

    # Find incoming log
    incoming_log = next((rec for rec in log_records if rec.message == "Incoming request"), None)
    assert incoming_log is not None
    assert incoming_log.levelname == "INFO"
    assert getattr(incoming_log, 'method', None) == "GET"
    assert getattr(incoming_log, 'path', None) == "/test/success"
    assert "client" in incoming_log.__dict__ # Check client info exists

    # Find outgoing log
    outgoing_log = next((rec for rec in log_records if rec.message == "Outgoing response"), None)
    assert outgoing_log is not None
    assert outgoing_log.levelname == "INFO"
    assert getattr(outgoing_log, 'method', None) == "GET"
    assert getattr(outgoing_log, 'path', None) == "/test/success"
    assert getattr(outgoing_log, 'status_code', None) == 200
    assert "process_time_ms" in outgoing_log.__dict__ # Check process time exists

@pytest.mark.asyncio
async def test_request_logging_middleware_error(local_middleware_client, caplog): # Use renamed fixture
    """Verify logs when an error occurs (handled by ErrorHandlerMiddleware)."""
    caplog.set_level(logging.INFO)

    response = await local_middleware_client.get("/test/generic_exception") # Use renamed fixture

    assert response.status_code == 500 # ErrorHandlerMiddleware should return 500

    # Check log records from RequestLoggingMiddleware
    # Filter logs specifically from the RequestLoggingMiddleware based on logger name
    log_records = [rec for rec in caplog.records if rec.name == 'opscore.middleware']

    assert len(log_records) >= 2 # Expect at least one incoming and one outgoing log

    # Find incoming log
    incoming_log = next((rec for rec in log_records if rec.message == "Incoming request"), None)
    assert incoming_log is not None
    assert getattr(incoming_log, 'method', None) == "GET"
    assert getattr(incoming_log, 'path', None) == "/test/generic_exception"

    # Find outgoing log (error case) - This log comes from the RequestLoggingMiddleware's except block
    outgoing_log = next((rec for rec in log_records if rec.message == "Outgoing response (error occurred)"), None)
    assert outgoing_log is not None
    assert outgoing_log.levelname == "INFO"
    assert getattr(outgoing_log, 'method', None) == "GET"
    assert getattr(outgoing_log, 'path', None) == "/test/generic_exception"
    # The status code logged here reflects the state *before* ErrorHandlerMiddleware creates the final 500 response
    assert getattr(outgoing_log, 'status_code', None) is not None
    assert "process_time_ms" in outgoing_log.__dict__

# --- ErrorHandlerMiddleware Tests ---

@pytest.mark.asyncio
async def test_error_handler_opscore_error_agent_not_found(local_middleware_client, caplog): # Use renamed fixture
    """Verify handling of a specific OpsCoreError (AgentNotFoundError)."""
    caplog.set_level(logging.ERROR)
    error_instance = AgentNotFoundError("test-agent-id")
    expected_status = get_status_code_for_exception(error_instance) # Should be 404
    expected_detail = str(error_instance)

    response = await local_middleware_client.get("/test/agent_not_found") # Use renamed fixture

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}

    # Check error log from ErrorHandlerMiddleware
    error_log = next((rec for rec in caplog.records if rec.levelname == "ERROR" and "OpsCoreError occurred" in rec.message), None)
    assert error_log is not None
    assert expected_detail in error_log.message
    assert getattr(error_log, 'error_type', None) == "AgentNotFoundError"
    assert getattr(error_log, 'status_code', None) == expected_status
    assert getattr(error_log, 'path', None) == "/test/agent_not_found"

@pytest.mark.asyncio
async def test_error_handler_opscore_error_invalid_state(local_middleware_client, caplog): # Use renamed fixture
    """Verify handling of a specific OpsCoreError (InvalidStateError)."""
    caplog.set_level(logging.ERROR)
    error_instance = InvalidStateError("Invalid state provided")
    expected_status = get_status_code_for_exception(error_instance) # Should be 400
    expected_detail = str(error_instance)

    response = await local_middleware_client.get("/test/invalid_state") # Use renamed fixture

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}

    # Check error log
    error_log = next((rec for rec in caplog.records if rec.levelname == "ERROR" and "OpsCoreError occurred" in rec.message), None)
    assert error_log is not None
    assert expected_detail in error_log.message
    assert getattr(error_log, 'error_type', None) == "InvalidStateError"
    assert getattr(error_log, 'status_code', None) == expected_status
    assert getattr(error_log, 'path', None) == "/test/invalid_state"

@pytest.mark.asyncio
async def test_error_handler_generic_exception(local_middleware_client, caplog): # Use renamed fixture
    """Verify handling of an unexpected generic Exception."""
    caplog.set_level(logging.CRITICAL) # Unhandled exceptions are logged as CRITICAL
    expected_status = 500
    expected_detail = "Internal Server Error"

    response = await local_middleware_client.get("/test/generic_exception") # Use renamed fixture

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}

    # Check critical log
    critical_log = next((rec for rec in caplog.records if rec.levelname == "CRITICAL" and "Unhandled exception occurred" in rec.message), None)
    assert critical_log is not None
    assert "Something unexpected went wrong" in critical_log.message # Original error message in log
    assert getattr(critical_log, 'error_type', None) == "ValueError"
    assert getattr(critical_log, 'status_code', None) == expected_status
    assert getattr(critical_log, 'path', None) == "/test/generic_exception"
    assert "traceback" in critical_log.__dict__ # Check traceback was logged

@pytest.mark.asyncio
async def test_error_handler_does_not_catch_http_exception(local_middleware_client, caplog): # Use renamed fixture
    """Verify that standard HTTPExceptions raised by routes are not caught."""
    caplog.set_level(logging.ERROR)
    expected_status = 418 # I'm a teapot
    expected_detail = "I'm a teapot"

    response = await local_middleware_client.get("/test/http_exception") # Use renamed fixture

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}

    # Ensure no ERROR or CRITICAL logs were generated by our ErrorHandlerMiddleware
    error_logs = [rec for rec in caplog.records if rec.levelname in ("ERROR", "CRITICAL") and rec.name == 'opscore.middleware']
    assert len(error_logs) == 0