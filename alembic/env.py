import asyncio # Import asyncio
import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file in the project root
# Assumes alembic is run from the ops_core directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Import async engine creation
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add the src directory to the Python path for src layout
# This allows Alembic to find your models like src.ops_core.models
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, src_path)

# Import your models and the shared metadata object
# Ensure all models that should be tracked by Alembic are imported here
from ops_core.models.tasks import Task # Import the Task model
# Import the shared metadata object from the models package
from ops_core.models.base import metadata as target_metadata # Use the shared metadata from base

# Import the application config loader to get the database URL
from ops_core.config.loader import get_resolved_mcp_config # Use src prefix

# The target_metadata is now imported directly from the models package

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    """Return the database URL from application configuration."""
    app_config = get_resolved_mcp_config()
    return app_config.database_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""

    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url() # Set the URL dynamically

    # Use async_engine_from_config for async driver
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Acquire connection asynchronously
    async with connectable.connect() as connection:
        # Run migrations within the async transaction context
        await connection.run_sync(do_run_migrations)

    # Dispose the engine
    await connectable.dispose()

def do_run_migrations(connection):
    """Helper function to run migrations within a transaction context."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    # Run the async migrations function using asyncio.run()
    asyncio.run(run_async_migrations())
