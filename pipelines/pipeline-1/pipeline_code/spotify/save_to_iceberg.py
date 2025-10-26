import duckdb

# Initialize DuckDB
con = duckdb.connect()

# Install and load extensions
con.execute("INSTALL iceberg;")
con.execute("LOAD iceberg;")
con.execute("INSTALL httpfs;")
con.execute("LOAD httpfs;")

print("✓ Extensions loaded")

# Configure S3 (MinIO) - use YOUR credentials from .env
con.execute("""
    SET s3_endpoint='localhost:9000';
    SET s3_access_key_id='admin';
    SET s3_secret_access_key='minio08062013';
    SET s3_region='eu-east-1';
    SET s3_use_ssl='false';
    SET s3_url_style='path';
""")

print("✓ S3 configured")

# Attach to Iceberg REST catalog
con.execute("""
    ATTACH 'iceberg_rest://localhost:8181' AS lakehouse 
    (TYPE ICEBERG)
""")

print("✓ Connected to Iceberg REST catalog")

# Create namespace for Spotify data
con.execute("CREATE SCHEMA IF NOT EXISTS lakehouse.spotify;")

print("✓ Schema created")

# Define your Spotify data path
bucket_name = 'ingestion'  # Your existing ingestion bucket
path_to_parquet_files = f's3://{bucket_name}/raw/spotify/api/daily/*.parquet'

# Create Iceberg table from your Spotify Parquet files
try:
    con.execute(f"""
        CREATE OR REPLACE TABLE lakehouse.spotify.listening_history AS
        SELECT 
            STRFTIME(CAST("played_at_dt" AS TIMESTAMP), '%Y-%m-%d %H:%M:%S') AS played_at_ts,
            track.name AS track_name,
            track.album.name AS album_name,
            track.artists[1].name AS artist_name,
            track.uri AS spotify_track_uri,
            track.duration_ms AS duration_ms
        FROM read_parquet('{path_to_parquet_files}')
    """)
    
    print("✓ Iceberg table created successfully!")
    
    # Verify the table
    row_count = con.execute("""
        SELECT COUNT(*) as count 
        FROM lakehouse.spotify.listening_history
    """).fetchone()[0]
    
    print(f"✓ Table contains {row_count:,} rows")
    
    # Show sample data
    print("\nSample data:")
    result = con.execute("""
        SELECT * 
        FROM lakehouse.spotify.listening_history 
        ORDER BY played_at_ts DESC
        LIMIT 5
    """).fetchdf()
    
    print(result)
    
    # Show your top artists
    print("\n🎵 Your Top 10 Artists:")
    top_artists = con.execute("""
        SELECT 
            artist_name,
            COUNT(*) as play_count,
            ROUND(SUM(duration_ms) / 1000.0 / 60.0, 2) as total_minutes
        FROM lakehouse.spotify.listening_history
        GROUP BY artist_name
        ORDER BY play_count DESC
        LIMIT 10
    """).fetchdf()
    
    print(top_artists)

except Exception as e:
    print(f"❌ Error creating Iceberg table: {e}")
    import traceback
    traceback.print_exc()