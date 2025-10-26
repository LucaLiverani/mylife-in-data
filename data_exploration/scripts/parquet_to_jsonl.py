
import os
import sys
from pathlib import Path
import pandas as pd
import json
import gzip
import s3fs
from dotenv import load_dotenv
import pendulum
import tempfile

# Load environment variables from .env file
load_dotenv()

# Add project root to sys.path to allow imports from 'src'
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path.cwd().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
    print(f"✓ Added project root to sys.path: {PROJECT_ROOT}")

from src.duckdb_config import DuckDBConnection

def create_ingestion_metadata(played_at_str):
    """Creates a dictionary with faked ingestion metadata based on played_at."""
    try:
        # Use pendulum to parse the timestamp string
        played_at_dt = pendulum.parse(played_at_str)
        execution_date = played_at_dt.start_of('day').isoformat()
        run_id = f"manual__{played_at_dt.to_iso8601_string()}"
    except (ValueError, TypeError):
        # Fallback if parsing fails
        now = pendulum.now('UTC')
        played_at_dt = now
        execution_date = now.start_of('day').isoformat()
        run_id = f"manual__{now.to_iso8601_string()}"
        played_at_str = now.isoformat()

    return {
        'ingested_at': played_at_str,
        'execution_date': execution_date,
        'dag_id': 'spotify_raw_ingestion_jsonl',  # Faking the DAG ID
        'run_id': run_id,
        'source': 'spotify_api',
    }

def get_s3_fs():
    """Initializes and returns an S3FileSystem object."""
    return s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": f'http://{os.getenv("MINIO_ENDPOINT", "localhost:9000")}'},
        key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    )

def get_jsonl_sample_structure(s3, bucket_name):
    """Reads the first line of a .jsonl.gz file from S3 to determine its structure."""
    tracks_path = f"{bucket_name}/raw/spotify/api/tracks"
    try:
        # Find the first available .jsonl.gz file
        jsonl_files = s3.glob(f"{tracks_path}/*.jsonl.gz")
        if not jsonl_files:
            print("No existing JSONL files found to match structure.")
            return None
        
        sample_file_path = jsonl_files[0]
        print(f"✓ Using '{sample_file_path}' as a structure reference.")

        with s3.open(sample_file_path, "rb") as f:
            with gzip.GzipFile(fileobj=f) as gz:
                first_line = gz.readline()
                if not first_line:
                    return None
                sample_data = json.loads(first_line)
                return set(sample_data.keys())
    except Exception as e:
        print(f"✗ Could not read sample JSONL file structure: {e}")
        return None

def validate_structure(new_record, expected_structure):
    """Validates if the new record's structure matches the expected one."""
    return set(new_record.keys()) == expected_structure

def convert_parquet_to_jsonl_s3():
    """
    Converts Parquet files to JSONL, validating their structure against existing files.
    """
    db = DuckDBConnection()
    con = db.connect()
    s3 = get_s3_fs()

    bucket_name = os.getenv("MINIO_BUCKET", "inbound")
    parquet_path_glob = f"s3://{bucket_name}/raw/spotify/api/daily/*.parquet"
    output_path_prefix = f"{bucket_name}/raw/spotify/api/tracks"

    # Get the expected structure from an existing JSONL file
    expected_structure = get_jsonl_sample_structure(s3, bucket_name)
    if not expected_structure:
        print("✗ Cannot proceed without a reference structure. Exiting.")
        return

    try:
        parquet_files_df = con.execute(f"SELECT file FROM glob('{parquet_path_glob}')").df()
        parquet_files = parquet_files_df["file"].tolist()
        if not parquet_files:
            print("No Parquet files found to convert.")
            return
        print(f"✓ Found {len(parquet_files)} parquet files to convert.")
    except Exception as e:
        print(f"✗ Error listing S3 Parquet files: {e}")
        return

    for parquet_file in parquet_files:
        try:
            print(f"Processing '{parquet_file}'...")
            df = con.execute(f"SELECT track, played_at, context FROM read_parquet('{parquet_file}')").df()
            records = df.to_dict("records")

            # Create a temporary file to write the JSONL content
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl.gz") as temp_f:
                with gzip.GzipFile(filename=temp_f.name, mode="wb") as gz:
                    is_structure_valid = True
                    for record in records:
                        raw_item = {
                            "track": record.get("track"),
                            "played_at": record.get("played_at"),
                            "context": record.get("context"),
                        }
                        json_record = {
                            "raw_item": raw_item,
                            "_ingestion_metadata": create_ingestion_metadata(record.get("played_at"))
                        }

                        # Validate the structure of the first record
                        if not validate_structure(json_record, expected_structure):
                            print(f"✗ Structure mismatch in '{parquet_file}'. Expected: {expected_structure}, Got: {set(json_record.keys())}")
                            is_structure_valid = False
                            break
                        
                        gz.write((json.dumps(json_record) + "\n").encode("utf-8"))
                
                if not is_structure_valid:
                    continue

                # Upload the validated temporary file to S3
                date_str = Path(parquet_file).stem
                jsonl_s3_path = f"{output_path_prefix}/{date_str}.jsonl.gz"
                s3.upload(temp_f.name, jsonl_s3_path)
                print(f"✓ Successfully converted and uploaded to 's3://{jsonl_s3_path}'")

        except Exception as e:
            print(f"✗ Error processing file '{parquet_file}': {e}")
        finally:
            # Clean up the temporary file
            if 'temp_f' in locals() and os.path.exists(temp_f.name):
                os.remove(temp_f.name)

if __name__ == "__main__":
    convert_parquet_to_jsonl_s3()
