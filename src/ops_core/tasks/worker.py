"""
Dramatiq worker entry point for Ops Core.

This script imports the necessary broker configuration and task actors
so that the Dramatiq worker process can discover and execute tasks.

To run the worker, use the Dramatiq CLI:
dramatiq ops_core.tasks.worker
"""

import logging

# Configure logging for the worker (optional but recommended)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Initializing Dramatiq worker...")

# Import the broker configuration. This sets up the connection
# and allows Dramatiq to find the broker.
from . import broker # noqa: F401 - Imported for side effects (broker registration)

# Import modules containing Dramatiq actors so they are discovered.
from src.ops_core.scheduler import engine # noqa: F401 - Imports execute_agent_task_actor

logger.info("Dramatiq worker initialized. Actors discovered.")
logger.info(f"Broker configured: {broker.rabbitmq_broker}")

# The Dramatiq CLI will handle the rest (connecting, processing tasks)
