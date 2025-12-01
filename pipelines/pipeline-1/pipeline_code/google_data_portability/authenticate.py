"""
Authentication script for Google Data Portability API.

Run this script first to authenticate and cache your OAuth token.
Similar to the Spotify authentication flow.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_data_portability.data_portability_api import get_client_local


def main():
    """
    Run the authentication flow and create a cached token.
    """
    print("=" * 60)
    print("Google Data Portability API Authentication")
    print("=" * 60)
    print()

    # Check if client_secrets.json exists
    client_secrets_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'client_secrets.json'
    )

    if not os.path.exists(client_secrets_path):
        print("ERROR: client_secrets.json not found!")
        print()
        print("Please follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create OAuth 2.0 credentials (Desktop app)")
        print("3. Download the credentials JSON file")
        print(f"4. Save it as: {client_secrets_path}")
        print()
        return

    print("Client secrets found!")
    print()
    print("Requesting access to:")
    print("  - YouTube Activity Data (myactivity.youtube)")
    print("  - Maps Activity Data (myactivity.maps)")
    print()
    print("A browser window will open for authentication...")
    print("OAuth callback will use port 8888")
    print()

    try:
        # Create client with YouTube and Maps activity scopes
        client = get_client_local(
            scopes=['youtube_activity', 'maps_activity'],
            client_secrets_file=client_secrets_path,
            port=8888
        )

        print()
        print("✓ Authentication successful!")
        print()
        print("Token has been cached. You can now run export scripts.")
        print()

    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()