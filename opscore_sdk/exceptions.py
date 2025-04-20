"""Custom exceptions for the Ops-Core SDK."""

class OpsCoreSDKError(Exception):
    """Base exception for all Ops-Core SDK errors."""
    pass

class OpsCoreApiError(OpsCoreSDKError):
    """Raised when the Ops-Core API returns an error response."""
    def __init__(self, status_code: int, detail: str | dict | None = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ops-Core API Error {status_code}: {detail or 'No details provided'}")

class AuthenticationError(OpsCoreApiError):
    """Raised for authentication errors (401 or 403)."""
    def __init__(self, status_code: int, detail: str | dict | None = None):
        super().__init__(status_code, detail or "Authentication failed")

class NotFoundError(OpsCoreApiError):
    """Raised when a resource is not found (404)."""
    def __init__(self, status_code: int, detail: str | dict | None = None):
        super().__init__(status_code, detail or "Resource not found")

class ConnectionError(OpsCoreSDKError):
    """Raised for network or connection issues when contacting the API."""
    pass