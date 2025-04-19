# Plan for Task 3.3: API Middleware Implementation

This plan outlines the steps to implement middleware for structured logging and standardized error handling across API endpoints in the Ops-Core module.

## 1. Create Middleware Module
*   Create a new file: `opscore/middleware.py`.
*   This module will house the custom middleware functions/classes.

## 2. Implement Logging Middleware
*   Define an `async` function or class (e.g., `RequestLoggingMiddleware`) in `opscore/middleware.py`.
*   **Functionality:**
    *   Log incoming request details (method, path, client IP) at the start.
    *   Record the start time of the request.
    *   Allow the request to proceed to the next middleware or route handler.
    *   Record the end time.
    *   Log outgoing response details (status code) and the total processing time.
    *   Utilize the existing structured logger configured in `opscore/logging_config.py`.

## 3. Implement Error Handling Middleware
*   Define an `async` function or class (e.g., `ErrorHandlerMiddleware`) in `opscore/middleware.py`.
*   **Functionality:**
    *   Wrap the call to the next middleware/route handler in a `try...except` block.
    *   **Catch `OpsCoreError` Subclasses:** Intercept specific exceptions defined in `opscore/exceptions.py`.
        *   Map each caught `OpsCoreError` to its corresponding HTTP status code (leveraging or refining existing mappings).
        *   Return a standardized JSON response body, e.g., `{"detail": "Error description from exception"}`.
        *   Log the error details using the structured logger.
    *   **Catch Generic `Exception`:** Intercept any other unhandled exceptions.
        *   Log the full traceback for debugging purposes.
        *   Return a generic 500 Internal Server Error response with a standard JSON body, e.g., `{"detail": "Internal Server Error"}`. Avoid leaking internal details in the response.

## 4. Integrate Middleware into FastAPI App
*   In `opscore/api.py`:
    *   Import the newly created middleware components from `opscore/middleware.py`.
    *   Add the middleware to the `FastAPI` app instance using `app.add_middleware()`.
    *   **Order:** The `ErrorHandlerMiddleware` should generally be added *first* (outermost layer) to catch exceptions from all subsequent processing, including the logging middleware. The `RequestLoggingMiddleware` would typically follow.
    *   **Review Existing Handlers:** Evaluate if the existing `@app.exception_handler` decorators in `api.py` should be removed in favor of the centralized middleware approach. The middleware is generally preferred for consistency.

## 5. Testing
*   Create a new test file: `tests/test_middleware.py`.
*   **Logging Middleware Tests:**
    *   Verify that logs are generated for requests and responses.
    *   Check if request/response details (method, path, status, time) are correctly captured in logs.
*   **Error Handling Middleware Tests:**
    *   Create test client requests designed to trigger specific `OpsCoreError` subclasses. Verify the returned HTTP status code and JSON response body match the expected standardized format.
    *   Create test client requests designed to trigger generic `Exception`s. Verify a 500 status code and the generic JSON error response are returned.
    *   Verify that errors (both specific and generic) are logged appropriately.
*   **API Test Review:** Briefly review `tests/test_api.py` to ensure tests still pass, especially those checking error responses, and update if the standardized error format differs significantly.

## 6. Documentation
*   Add docstrings to the middleware functions/classes in `opscore/middleware.py` explaining their purpose.
*   Update `memory-bank/activeContext.md` and `memory-bank/progress.md` upon completion.

## Visual Representation

```mermaid
graph TD
    subgraph FastAPI Request Pipeline
        direction LR
        Request --> ErrorMiddleware[ErrorHandlerMiddleware]
        ErrorMiddleware --> LoggingMiddleware[RequestLoggingMiddleware]
        LoggingMiddleware --> RouteHandler[API Route Handler]
        RouteHandler --> LoggingMiddleware
        LoggingMiddleware --> ErrorMiddleware
        ErrorMiddleware --> Response[HTTP Response]
    end

    ErrorMiddleware -- Catches OpsCoreError --> FormatStandardError[Format Standard JSON Error (e.g., 4xx)]
    ErrorMiddleware -- Catches Exception --> FormatGenericError[Format Generic JSON Error (500)]
    FormatStandardError --> Response
    FormatGenericError --> Response

    LoggingMiddleware -- Logs Request Info --> StructuredLogger[Structured Logger]
    LoggingMiddleware -- Logs Response Info --> StructuredLogger

    RouteHandler -- Raises Error --> ErrorMiddleware
    RouteHandler -- Returns Success --> LoggingMiddleware