"""
Spotify transformation SQL templates.
"""


class SpotifyTransformer:
    """SQL templates for Spotify transformations"""
    
    @staticmethod
    def get_bronze_query(s3_path: str = "s3://inbound/raw/spotify/api/tracks/*.jsonl.gz") -> str:
        """
        DuckDB SQL to transform raw JSONL to Bronze schema.
        
        This reads directly from S3 and flattens the nested structure!
        """
        return f"""
        WITH raw_data AS (
            SELECT * FROM read_json_auto('{s3_path}')
        )
        SELECT 
            -- Track identifiers
            raw_item.track.id::VARCHAR AS track_id,
            raw_item.track.name::VARCHAR AS track_name,
            raw_item.track.uri::VARCHAR AS track_uri,
            
            -- Artist info (first artist)
            raw_item.track.artists[1].name::VARCHAR AS artist_name,
            raw_item.track.artists[1].id::VARCHAR AS artist_id,
            
            -- All artists (comma-separated)
            list_transform(
                raw_item.track.artists, 
                x -> x.name
            )::VARCHAR[] AS all_artist_names,
            list_transform(
                raw_item.track.artists, 
                x -> x.id
            )::VARCHAR[] AS all_artist_ids,
            
            -- Album info
            raw_item.track.album.name::VARCHAR AS album_name,
            raw_item.track.album.id::VARCHAR AS album_id,
            raw_item.track.album.album_type::VARCHAR AS album_type,
            TRY_CAST(raw_item.track.album.release_date AS DATE) AS album_release_date,
            
            -- Track metadata
            raw_item.track.duration_ms::INTEGER AS duration_ms,
            COALESCE(raw_item.track.explicit, false)::BOOLEAN AS explicit,
            raw_item.track.popularity::INTEGER AS popularity,
            COALESCE(raw_item.track.is_local, false)::BOOLEAN AS is_local,
            
            -- Play context
            TRY_CAST(raw_item.played_at AS TIMESTAMP) AS played_at,
            DATE_TRUNC('day', TRY_CAST(raw_item.played_at AS TIMESTAMP)) AS played_date,
            raw_item.context.type::VARCHAR AS context_type,
            raw_item.context.uri::VARCHAR AS context_uri,
            
            -- Ingestion metadata
            TRY_CAST(_ingestion_metadata.ingested_at AS TIMESTAMP) AS ingested_at,
            TRY_CAST(_ingestion_metadata.execution_date AS TIMESTAMP) AS execution_date,
            _ingestion_metadata.dag_id::VARCHAR AS dag_id,
            _ingestion_metadata.run_id::VARCHAR AS run_id,
            _ingestion_metadata.source::VARCHAR AS source
            
        FROM raw_data
        WHERE 
            raw_item.track.id IS NOT NULL 
            AND raw_item.played_at IS NOT NULL
        """
    
    @staticmethod
    def get_bronze_query_for_dates(dates: list[str]) -> str:
        """
        Generate query for specific dates.
        
        Args:
            dates: List of date strings like ['2025-10-29', '2025-10-30']
        
        Returns:
            SQL query with file paths for those dates
        """
        file_paths = [
            f"'s3://inbound/raw/spotify/api/tracks/{date}.jsonl.gz'"
            for date in dates
        ]
        
        # Use read_json for multiple specific files
        files_str = ", ".join(file_paths)
        
        return f"""
        WITH raw_data AS (
            SELECT * FROM read_json_auto([{files_str}])
        )
        SELECT 
            -- (same SELECT clause as above)
            raw_item.track.id::VARCHAR AS track_id,
            raw_item.track.name::VARCHAR AS track_name,
            raw_item.track.uri::VARCHAR AS track_uri,
            raw_item.track.artists[1].name::VARCHAR AS artist_name,
            raw_item.track.artists[1].id::VARCHAR AS artist_id,
            raw_item.track.album.name::VARCHAR AS album_name,
            raw_item.track.album.id::VARCHAR AS album_id,
            raw_item.track.duration_ms::INTEGER AS duration_ms,
            TRY_CAST(raw_item.played_at AS TIMESTAMP) AS played_at,
            DATE_TRUNC('day', TRY_CAST(raw_item.played_at AS TIMESTAMP)) AS played_date,
            TRY_CAST(_ingestion_metadata.ingested_at AS TIMESTAMP) AS ingested_at,
            _ingestion_metadata.dag_id::VARCHAR AS dag_id
        FROM raw_data
        WHERE 
            raw_item.track.id IS NOT NULL 
            AND raw_item.played_at IS NOT NULL
        """