"""
Base definitions for SQLModel models, including a shared MetaData instance.
"""

from sqlalchemy import MetaData

# Define a shared MetaData instance to be used by all SQLModel table models
# This helps prevent errors during test collection where models might be imported multiple times.
metadata = MetaData()
