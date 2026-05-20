"""
Export YouTube activity data using Google Data Portability API.

This script initiates an export job for YouTube viewing history and activity,
waits for it to complete, and downloads the resulting archive.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_data_portability.data_portability_api import get_client_local


def main():
    parser = argparse.ArgumentParser(
        description='Export YouTube activity data via Data Portability API'
    )
    parser.add_argument(
        '--start-date',
        help='Start date for data export (YYYY-MM-DD)',
        type=str
    )
    parser.add_argument(
        '--end-date',
        help='End date for data export (YYYY-MM-DD)',
        type=str
    )
    parser.add_argument(
        '--output-dir',
        help='Output directory for downloaded files',
        default='data/google_exports/youtube',
        type=str
    )
    parser.add_argument(
        '--poll-interval',
        help='Seconds between status checks',
        default=30,
        type=int
    )

    args = parser.parse_args()

    print("=" * 60)
    print("YouTube Data Export")
    print("=" * 60)
    print()

    # Initialize client
    client_secrets_path = os.path.join(
        os.path.dirname(__file__), '..', 'client_secrets.json'
    )

    print("Initializing Data Portability API client...")
    client = get_client_local(
        scopes=['youtube_activity'],
        client_secrets_file=client_secrets_path
    )
    print()

    # Prepare time filters if provided
    start_time = None
    end_time = None

    if args.start_date:
        start_time = f"{args.start_date}T00:00:00Z"
        print(f"Start date: {args.start_date}")

    if args.end_date:
        end_time = f"{args.end_date}T23:59:59Z"
        print(f"End date: {args.end_date}")

    if not start_time and not end_time:
        print("No time filters specified - exporting ALL YouTube activity data")

    print()

    # Initiate export
    print("Initiating YouTube data export...")
    response = client.initiate_archive(
        resources=['myactivity.youtube'],
        start_time=start_time,
        end_time=end_time
    )

    archive_job_id = response.get('archiveJobId')
    print(f"Archive job ID: {archive_job_id}")
    print()

    # Wait for completion
    print("Waiting for export to complete...")
    print("(This may take several minutes to several hours depending on data size)")
    print()

    try:
        state, urls = client.wait_for_archive(
            archive_job_id,
            poll_interval=args.poll_interval,
            max_wait_time=7200  # 2 hours max
        )

        # Download files
        print()
        print(f"Downloading {len(urls)} file(s)...")
        print()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(args.output_dir, f"export_{timestamp}")

        for idx, url in enumerate(urls, 1):
            filename = f"youtube_data_part_{idx}.zip"
            output_path = os.path.join(output_dir, filename)
            print(f"[{idx}/{len(urls)}] {filename}")
            client.download_archive_file(url, output_path)

        print()
        print("=" * 60)
        print("✓ YouTube data export complete!")
        print("=" * 60)
        print(f"Files saved to: {output_dir}")
        print()

    except Exception as e:
        print()
        print(f"✗ Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()