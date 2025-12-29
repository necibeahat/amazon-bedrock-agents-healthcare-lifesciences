"""Storage configuration utilities."""

import os
from typing import Optional

from .storage_manager import StorageManager


def create_storage_manager_from_env() -> Optional[StorageManager]:
    """Create a StorageManager instance from environment variables.
    
    Expected environment variables:
    - DATABASE_URL: PostgreSQL connection string
    - DB_SCHEMA: Database schema name (optional, defaults to 'pharma_pipeline')
    
    Returns:
        StorageManager instance or None if configuration is missing
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    
    schema_name = os.getenv("DB_SCHEMA", "pharma_pipeline")
    
    try:
        return StorageManager(
            connection_string=database_url,
            schema_name=schema_name
        )
    except Exception as e:
        print(f"Failed to create storage manager: {e}")
        return None


def create_storage_manager_from_config(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    schema_name: str = "pharma_pipeline"
) -> StorageManager:
    """Create a StorageManager instance from configuration parameters.
    
    Args:
        host: Database host
        port: Database port
        database: Database name
        username: Database username
        password: Database password
        schema_name: Database schema name
        
    Returns:
        StorageManager instance
    """
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    return StorageManager(
        connection_string=connection_string,
        schema_name=schema_name
    )