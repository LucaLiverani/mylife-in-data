"""
Centralized DuckDB configuration with S3/MinIO support.
"""

import duckdb
import logging
from typing import Optional, Any
from contextlib import contextmanager

log = logging.getLogger(__name__)


class DuckDBConfig:
    """
    Manages DuckDB connections with S3/MinIO configuration.
    Singleton pattern to reuse connections.
    """
    
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_connection(
        cls,
        database: str = ":memory:",
        read_only: bool = False,
        s3_endpoint: str = "minio:9000",
        s3_access_key: str = "minioadmin",
        s3_secret_key: str = "minioadmin",
        s3_use_ssl: bool = False,
        threads: Optional[int] = None,
    ) -> duckdb.DuckDBPyConnection:
        """
        Get or create a DuckDB connection with S3 configuration.
        
        Args:
            database: Database path (:memory: for in-memory)
            read_only: Open in read-only mode
            s3_endpoint: S3/MinIO endpoint
            s3_access_key: S3 access key
            s3_secret_key: S3 secret key
            s3_use_ssl: Use HTTPS for S3
            threads: Number of threads (default: CPU count)
        
        Returns:
            DuckDB connection
        """
        if cls._connection is not None:
            return cls._connection
        
        log.info(f"Initializing DuckDB connection: {database}")
        
        # Create connection
        con = duckdb.connect(database=database, read_only=read_only)
        
        # Install and load extensions
        extensions = ['httpfs', 'json', 'parquet']
        for ext in extensions:
            try:
                con.execute(f"INSTALL {ext};")
                con.execute(f"LOAD {ext};")
                log.info(f"Loaded extension: {ext}")
            except Exception as e:
                log.warning(f"Failed to load extension {ext}: {e}")
        
        # Configure S3/MinIO
        con.execute(f"SET s3_endpoint='{s3_endpoint}';")
        con.execute(f"SET s3_access_key_id='{s3_access_key}';")
        con.execute(f"SET s3_secret_access_key='{s3_secret_key}';")
        con.execute(f"SET s3_use_ssl={'true' if s3_use_ssl else 'false'};")
        con.execute("SET s3_url_style='path';")  # Important for MinIO
        
        # Performance tuning
        if threads:
            con.execute(f"SET threads={threads};")
        
        # Set memory limits (adjust based on your environment)
        con.execute("SET memory_limit='4GB';")
        con.execute("SET temp_directory='/tmp/duckdb';")

        log.info("DuckDB configured for S3/MinIO")

        cls._connection = con
        return cls._connection
    
    @classmethod
    def close(cls):
        """Close the connection"""
        if cls._connection:
            cls._connection.close()
            cls._connection = None
            log.info("DuckDB connection closed")


def get_duckdb_connection(**kwargs) -> duckdb.DuckDBPyConnection:
    """
    Convenience function to get a configured DuckDB connection.
    """
    return DuckDBConfig.get_connection(**kwargs)


@contextmanager
def duckdb_session(**kwargs):
    """
    Context manager for DuckDB sessions.
    
    Usage:
        with duckdb_session() as con:
            result = con.execute("SELECT * FROM ...").df()
    """
    con = get_duckdb_connection(**kwargs)
    try:
        yield con
    finally:
        # Don't close - reuse connection
        pass


def query(sql: str, as_df: bool = True, **connection_kwargs) -> Any:
    """
    Execute a query and return results.
    
    Args:
        sql: SQL query string
        as_df: Return as pandas DataFrame (default: True)
        **connection_kwargs: Additional connection parameters
    
    Returns:
        Query results as DataFrame or DuckDB relation
    
    Example:
        df = query("SELECT * FROM 's3://bucket/data/*.parquet'")
    """
    con = get_duckdb_connection(**connection_kwargs)
    result = con.execute(sql)
    return result.df() if as_df else result


def explore(sql: str, limit: int = 1000, **connection_kwargs):
    """
    Quick exploration query with automatic limit.
    
    Args:
        sql: SQL query
        limit: Maximum rows to return
        **connection_kwargs: Connection parameters
    
    Returns:
        DataFrame with limited results
    """
    # Add LIMIT if not present
    if 'limit' not in sql.lower():
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    
    return query(sql, as_df=True, **connection_kwargs)


def test_s3_connection():
    """
    Test S3/MinIO connectivity.
    Returns True if successful.
    """
    try:
        con = get_duckdb_connection()
        result = con.execute("""
            SELECT COUNT(*) as file_count
            FROM glob('s3://inbound/raw/**/*.jsonl.gz')
        """).fetchone()

        log.info(f"S3 connection successful. Found {result[0]} files")
        return True
    except Exception as e:
        log.error(f"S3 connection failed: {e}")
        return False