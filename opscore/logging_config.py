"""
Ops-Core Logging Configuration

Sets up structured logging (JSON format) for the application.
"""

import logging
import json
import sys
from datetime import datetime, timezone # Import timezone

# --- JSON Formatter ---

class JsonFormatter(logging.Formatter):
    """
    Formats log records as JSON strings.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Use timezone-aware UTC time
        timestamp_aware = datetime.fromtimestamp(record.created, timezone.utc)
        log_entry = {
            # isoformat() includes timezone info (+00:00 for UTC)
            "timestamp": timestamp_aware.isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            # Basic formatting for exception to avoid breaking JSON
            log_entry["exception"] = self.formatException(record.exc_info).replace('"', '\\"')
        if hasattr(record, 'props') and isinstance(record.props, dict):
            log_entry.update(record.props) # Add custom properties

        # Add standard fields if available
        if record.pathname: log_entry["pathname"] = record.pathname
        if record.lineno: log_entry["lineno"] = record.lineno
        if record.funcName: log_entry["funcName"] = record.funcName

        # Attempt to add other extra fields safely
        standard_keys = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName', 'props', # Include props as it's handled specially
            'exception' # Include exception as it's handled specially
        }
        extra_keys = set(record.__dict__.keys()) - set(log_entry.keys()) - standard_keys
        for key in extra_keys:
             try:
                 json.dumps({key: record.__dict__[key]}) # Test serialization
                 log_entry[key] = record.__dict__[key]
             except TypeError:
                 log_entry[key] = repr(record.__dict__[key]) # Use repr for non-serializable types


        return json.dumps(log_entry)

# --- Configuration Function ---

_is_configured = False

def setup_logging(log_level: str = "INFO"):
    """
    Configures the root logger for JSON output to stdout.

    Args:
        log_level: The minimum log level to output (e.g., "DEBUG", "INFO", "WARNING").
    """
    global _is_configured
    if _is_configured:
        # logging.getLogger(__name__).debug("Logging already configured.")
        return

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates if re-run
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create a handler that writes to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create and set the JSON formatter
    formatter = JsonFormatter()
    handler.setFormatter(formatter)

    # Add the handler to the root logger
    root_logger.addHandler(handler)

    # Configure logging for libraries if needed (e.g., uvicorn, fastapi)
    logging.getLogger("uvicorn.error").propagate = False # Use uvicorn's own formatting for access logs if desired
    logging.getLogger("uvicorn.access").propagate = False
    # logging.getLogger("fastapi").setLevel(level) # Adjust level for FastAPI logs

    _is_configured = True
    root_logger.info(f"Logging configured with level {log_level.upper()}. Outputting JSON to stdout.")


def get_logger(name: str) -> logging.Logger:
    """
    Gets a logger instance, ensuring setup_logging has been called.

    Args:
        name: The name for the logger (typically __name__).

    Returns:
        A configured logger instance.
    """
    if not _is_configured:
        setup_logging() # Setup with default level if not already done
    return logging.getLogger(name)

# --- Example Usage (can be removed later) ---
if __name__ == "__main__":
    setup_logging(log_level="DEBUG")
    logger = get_logger(__name__)

    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")

    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Caught an exception.")

    # Example with extra properties
    logger.info("User logged in.", extra={'props': {'user_id': 123, 'ip_address': '192.168.1.1'}})