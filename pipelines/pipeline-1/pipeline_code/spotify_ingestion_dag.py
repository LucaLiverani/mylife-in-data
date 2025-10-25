from __future__ import annotations
import io
import logging
import pendulum
import pandas as pd
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable
from airflow.exceptions import AirflowException
from spotify.spotify_api import get_spotify_client, get_recently_played_tracks
from datetime import timedelta

# Get a logger
log = logging.getLogger(__name__)

def fetch_and_consolidate_spotify_data():
    """
    Fetches recently played tracks from Spotify since the last run and consolidates
    them into a daily Parquet file in S3.
    """
    log.info("Starting Spotify data fetch and consolidation task.")
    s3_hook = S3Hook(aws_conn_id="minio_s3")
    bucket_name = "inbound"
    variable_key = "spotify_last_played_at_timestamp"

    # Get the timestamp of the last processed track from Airflow Variables
    last_played_at = Variable.get(variable_key, default_var=None)
    if last_played_at:
        last_played_at = int(last_played_at)
        log.info(f"Found last_played_at timestamp: {last_played_at}")
    else:
        log.info("No last_played_at timestamp found. Will fetch all available recent tracks.")

    # Fetch new tracks from Spotify
    log.info("Fetching new tracks from Spotify API...")
    sp = get_spotify_client()
    recent_tracks = get_recently_played_tracks(sp, after=last_played_at)

    if not recent_tracks or not recent_tracks["items"]:
        log.info("No new tracks to process. Task finished.")
        return

    log.info(f"Fetched {len(recent_tracks['items'])} new tracks from Spotify.")

    # Process and group new tracks by date
    new_df = pd.DataFrame(recent_tracks["items"])
    new_df["played_at_dt"] = pd.to_datetime(new_df["played_at"])
    new_df["played_at_date"] = new_df["played_at_dt"].dt.date

    # Find the timestamp of the newest track to save for the next run
    newest_played_at = int(new_df["played_at_dt"].max().timestamp() * 1000)

    # Group tracks by the date they were played
    for played_date, tracks_df in new_df.groupby("played_at_date"):
        key = f"raw/spotify/api/daily/{played_date.strftime('%Y-%m-%d')}.parquet"
        log.info(f"Processing {len(tracks_df)} tracks for date: {played_date}")
        
        try:
            # Check if a file for this date already exists
            if s3_hook.check_for_key(key, bucket_name):
                log.info(f"Existing file found at s3://{bucket_name}/{key}. Merging data.")
                # Read existing data from S3
                s3_file = s3_hook.get_key(key, bucket_name)
                buffer = io.BytesIO(s3_file.get()["Body"].read())
                existing_df = pd.read_parquet(buffer)
                log.info(f"Existing file has {len(existing_df)} tracks.")
                
                # Combine with new data and remove duplicates
                combined_df = pd.concat([existing_df, tracks_df]).drop_duplicates(
                    subset=["played_at"], keep="first"
                )
                log.info(f"After merging, total tracks for this date: {len(combined_df)}.")
            else:
                log.info(f"No existing file found for this date. Creating new file at s3://{bucket_name}/{key}.")
                combined_df = tracks_df

            # Write the consolidated data back to S3
            buffer = io.BytesIO()
            combined_df.to_parquet(buffer)
            s3_hook.load_bytes(
                buffer.getvalue(),
                key=key,
                bucket_name=bucket_name,
                replace=True
            )
            log.info(f"Successfully wrote {len(combined_df)} tracks to s3://{bucket_name}/{key}.")

        except Exception as e:
            log.error(f"Error processing data for date {played_date}: {e}", exc_info=True)
            raise AirflowException(f"Failed to process data for {played_date}")

    # Update the Airflow Variable with the timestamp of the newest track
    log.info(f"Updating '{variable_key}' to new timestamp: {newest_played_at}")
    Variable.set(variable_key, str(newest_played_at))
    log.info("Spotify data fetch and consolidation task finished successfully.")

with DAG(
    dag_id="spotify_ingestion_dag",
    schedule_interval="*/15 * * * *",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    tags=["spotify", "ingestion"],
) as dag:
    PythonOperator(
        task_id="fetch_and_consolidate_spotify_data",
        python_callable=fetch_and_consolidate_spotify_data,
        execution_timeout=timedelta(minutes=5),
        retries=3,
        retry_delay=timedelta(minutes=1),
    )
