"""
Simplified Iceberg loader - uses DuckDB directly.
"""

from typing import Optional, Dict
import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.schema import Schema
from pyiceberg.partitioning import PartitionSpec
import logging

from libs.iceberg.catalog import get_default_catalog
from libs.iceberg.table_manager import IcebergTableManager
from libs.duckdb_config import get_duckdb_connection

log = logging.getLogger(__name__)


class IcebergLoader:
    """Simplified loader using DuckDB for transformations"""
    
    def __init__(self, catalog: Optional[Catalog] = None):
        self.catalog = catalog or get_default_catalog()
        self.table_manager = IcebergTableManager(self.catalog)
        self.con = get_duckdb_connection()
    
    def load_from_sql(
        self,
        sql: str,
        table_identifier: str,
        schema: Optional[Schema] = None,
        partition_spec: Optional[PartitionSpec] = None,
        mode: str = "append",  # "append" or "overwrite"
    ) -> Dict:
        """
        Load data from a SQL query directly into Iceberg.
        
        Args:
            sql: DuckDB SQL query (can read from S3 directly!)
            table_identifier: e.g., "bronze.spotify_tracks"
            schema: Optional Iceberg schema (auto-inferred if None)
            partition_spec: Optional partition spec
            mode: "append" or "overwrite"
        
        Returns:
            Loading statistics
        
        Example:
            loader.load_from_sql(
                sql="SELECT * FROM 's3://bucket/data/*.jsonl.gz'",
                table_identifier="bronze.my_table"
            )
        """
        log.info(f"Loading data to {table_identifier}...")
        log.debug(f"SQL: {sql}")
        
        # 1. Execute query and get Arrow table
        arrow_table = self.con.execute(sql).arrow()
        
        if arrow_table.num_rows == 0:
            log.warning("Query returned 0 rows")
            return {"status": "no_data", "records": 0}
        
        log.info(f"Query returned {arrow_table.num_rows} rows, {arrow_table.num_columns} columns")
        
        # 2. Infer schema if not provided
        if schema is None:
            schema = self.table_manager.infer_iceberg_schema_from_arrow(arrow_table.schema)
        
        # 3. Ensure namespace exists
        namespace = table_identifier.split('.')[0]
        self.table_manager.ensure_namespace(namespace)
        
        # 4. Create table if not exists
        self.table_manager.create_table_if_not_exists(
            table_identifier=table_identifier,
            schema=schema,
            partition_spec=partition_spec,
        )
        
        # 5. Load table
        table = self.catalog.load_table(table_identifier)
        
        # 6. Write data
        if mode == "overwrite":
            log.info("Overwriting table...")
            table.overwrite(arrow_table)
        else:  # append
            log.info("Appending to table...")
            table.append(arrow_table)

        log.info(f"Loaded {arrow_table.num_rows} records to {table_identifier}")
        
        return {
            "status": "success",
            "table": table_identifier,
            "records": arrow_table.num_rows,
            "mode": mode,
        }
    
    def load_incremental_from_sql(
        self,
        sql: str,
        table_identifier: str,
        unique_key: str,
    ) -> Dict:
        """
        Load with deduplication (delete + insert pattern).
        
        Args:
            sql: SQL query returning data to load
            table_identifier: Target table
            unique_key: Column to use for deduplication
        
        Returns:
            Loading statistics
        """
        log.info(f"Incremental load with deduplication on: {unique_key}")
        
        # 1. Execute query to get new data
        arrow_table = self.con.execute(sql).arrow()
        
        if arrow_table.num_rows == 0:
            return {"status": "no_data", "records": 0}
        
        # 2. Extract unique key values
        unique_values = arrow_table.column(unique_key).to_pylist()
        unique_values = list(set(v for v in unique_values if v is not None))
        
        log.info(f"Deduplicating {len(unique_values)} unique keys...")
        
        # 3. Load table
        table = self.catalog.load_table(table_identifier)
        
        # 4. Delete existing records
        if unique_values:
            from pyiceberg.expressions import In
            table.delete(In(unique_key, unique_values))
            log.info(f"Deleted existing records for {len(unique_values)} keys")
        
        # 5. Append new data
        table.append(arrow_table)

        log.info(f"Loaded {arrow_table.num_rows} records to {table_identifier}")
        
        return {
            "status": "success",
            "table": table_identifier,
            "records": arrow_table.num_rows,
            "unique_keys_processed": len(unique_values),
            "mode": "incremental",
        }