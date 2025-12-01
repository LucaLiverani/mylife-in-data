"""
Check the status of an existing Data Portability export job.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_data_portability.data_portability_api import get_client_local


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_job_status.py <job_id>")
        print()
        print("Example: python check_job_status.py 490362e0-2a02-4e7a-95f3-741380910345")
        sys.exit(1)

    job_id = sys.argv[1]

    client_secrets_path = os.path.join(
        os.path.dirname(__file__), '..', 'client_secrets.json'
    )

    print(f"Checking status of job: {job_id}")
    print()

    # Initialize client
    client = get_client_local(
        scopes=['youtube_activity', 'maps_activity'],
        client_secrets_file=client_secrets_path,
        port=8888
    )

    try:
        state = client.get_archive_state(job_id)

        job_state = state.get('state', 'UNKNOWN')
        print(f"Job State: {job_state}")
        print()

        if job_state == 'COMPLETE':
            urls = state.get('urls', [])
            print(f"✓ Job complete! {len(urls)} file(s) ready for download")
            print()
            print("Download URLs:")
            for idx, url in enumerate(urls, 1):
                print(f"  {idx}. {url[:100]}...")
        elif job_state in ['IN_PROGRESS', 'INITIATED']:
            print("Job is still processing. Please wait and check again later.")
        elif job_state == 'FAILED':
            print("✗ Job failed")
            print(f"Details: {state}")
        else:
            print(f"Unknown state: {state}")

    except Exception as e:
        print(f"✗ Error checking job status: {e}")


if __name__ == "__main__":
    main()
