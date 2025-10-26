"""DuckDB connection and configuration utilities."""

import os
import sys
from typing import Optional
from pathlib import Path

import duckdb
from dotenv import load_dotenv

# Add project root to sys.path to allow clean imports from 'src'
# This allows notebooks in 'notebooks/' to import from 'src/'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Load environment variables
load_dotenv()


class DuckDBConnection:
    """Manages DuckDB connections with MinIO configuration."""

    def __init__(
        self,
        database: Optional[str] = None,
        read_only: bool = False,
        memory_limit: str = "4GB",
        threads: int = 4,
    ):
        """
        Initialize DuckDB connection.

        Args:
            database: Path to database file. Use ':memory:' for in-memory.
            read_only: Whether to open in read-only mode.
            memory_limit: Memory limit for DuckDB (e.g., '4GB').
            threads: Number of threads for parallel execution.
        """
        self.database = database or os.getenv("DUCKDB_DATABASE", ":memory:")
        self.read_only = read_only
        self.memory_limit = memory_limit
        self.threads = threads
        self.con: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Establish connection to DuckDB."""
        if self.con is not None:
            return self.con

        self.con = duckdb.connect(
            database=self.database,
            read_only=self.read_only,
        )

        # Configure DuckDB
        self.con.execute(f"SET memory_limit='{self.memory_limit}'")
        self.con.execute(f"SET threads TO {self.threads}")

        # Install and load extensions
        self._setup_extensions()
        
        # Configure MinIO/S3
        self._setup_s3()

        return self.con

    def _setup_extensions(self):
        """Install and load required extensions."""
        extensions = ["httpfs", "parquet"]
        
        for ext in extensions:
            try:
                self.con.execute(f"INSTALL {ext}")
                self.con.execute(f"LOAD {ext}")
                print(f"✓ Loaded extension: {ext}")
            except Exception as e:
                print(f"✗ Failed to load extension {ext}: {e}")

    def _setup_s3(self):
        """Configure S3/MinIO access."""
        s3_config = {
            "s3_region": os.getenv("MINIO_REGION", "us-east-1"),
            "s3_endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            "s3_access_key_id": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            "s3_secret_access_key": os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            "s3_use_ssl": os.getenv("MINIO_USE_SSL", "false"),
            "s3_url_style": "path",
        }

        for key, value in s3_config.items():
            self.con.execute(f"SET {key}='{value}'")
        
        print(f"✓ Configured S3/MinIO: {s3_config['s3_endpoint']}")

    def query(self, sql: str, as_df: bool = True):
        """
        Execute query and return results.

        Args:
            sql: SQL query string.
            as_df: Return as pandas DataFrame (default: True).

        Returns:
            Query results as DataFrame or DuckDB relation.
        """
        if self.con is None:
            self.connect()
        
        result = self.con.execute(sql)
        return result.df() if as_df else result

    def close(self):
        """Close the connection."""
        if self.con is not None:
            self.con.close()
            self.con = None

    def __enter__(self):
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function
def get_connection(**kwargs) -> duckdb.DuckDBPyConnection:
    """
    Get a configured DuckDB connection.

    Args:
        **kwargs: Arguments passed to DuckDBConnection.

    Returns:
        Connected DuckDB connection object.
    """
    db = DuckDBConnection(**kwargs)
    return db.connect()


# Quick exploration helper
def explore(query: str, limit: Optional[int] = None):
    """
    Quick data exploration helper.

    Args:
        query: SQL query string.
        limit: Optional row limit.

    Returns:
        pandas DataFrame with results.
    """
    if limit:
        query = f"{query} LIMIT {limit}"
    
    db = DuckDBConnection()
    return db.query(query)