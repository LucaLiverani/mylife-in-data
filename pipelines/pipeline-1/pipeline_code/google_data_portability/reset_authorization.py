"""
Reset Data Portability authorization to allow re-exporting the same resources.

Use this if you get a 409 Conflict error when trying to initiate a new export.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_data_portability.data_portability_api import get_client_local


def main():
    client_secrets_path = os.path.join(
        os.path.dirname(__file__), '..', 'client_secrets.json'
    )

    print("=" * 60)
    print("Reset Data Portability Authorization")
    print("=" * 60)
    print()
    print("This will reset your authorization, allowing you to initiate")
    print("new export jobs for resources you've already exported.")
    print()

    # Initialize client
    print("Initializing client...")
    client = get_client_local(
        scopes=['youtube_activity', 'maps_activity'],
        client_secrets_file=client_secrets_path,
        port=8888
    )

    try:
        print("Resetting authorization...")
        result = client.reset_authorization()
        print()
        print("✓ Authorization reset successfully!")
        print()
        print("You can now initiate new export jobs.")
        print()

    except Exception as e:
        print()
        print(f"✗ Reset failed: {e}")
        print()
        print("If you get a 404 error, the API might not support reset,")
        print("or there might be no active authorization to reset.")
        sys.exit(1)


if __name__ == "__main__":
    main()
