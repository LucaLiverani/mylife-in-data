"""
Authentication script for Google Data Portability API.

Run this script first to authenticate and cache your OAuth token.
Similar to the Spotify authentication flow.

IMPORTANT: Before running this script, ensure your OAuth Consent Screen
is in 'Production' mode (not 'Testing') to avoid token expiration issues.
"""

import os
import sys
import json
import pickle
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from google_data_portability.data_portability_api import get_client_local


def check_existing_token():
    """Check if a token already exists and show its status."""
    token_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'tokens',
        '.google_portability_token.pickle'
    )

    if os.path.exists(token_path):
        print("\n" + "=" * 60)
        print("Existing Token Found")
        print("=" * 60)

        try:
            with open(token_path, 'rb') as f:
                creds = pickle.load(f)

            # Get token info
            file_stat = os.stat(token_path)
            file_modified = datetime.fromtimestamp(file_stat.st_mtime)
            days_old = (datetime.now() - file_modified).days

            print(f"Token file: {token_path}")
            print(f"Last modified: {file_modified.strftime('%Y-%m-%d %H:%M:%S')} ({days_old} days ago)")
            print(f"File size: {file_stat.st_size} bytes")
            print(f"Has refresh token: {bool(creds.refresh_token)}")
            print(f"Token valid: {creds.valid}")
            print(f"Token expired: {creds.expired if hasattr(creds, 'expired') else 'Unknown'}")

            if days_old > 7:
                print("\n⚠️  WARNING: Token is more than 7 days old")
                print("   If your OAuth Consent Screen is in 'Testing' mode, this token is expired!")

            print("=" * 60 + "\n")

        except Exception as e:
            print(f"Could not read token: {e}\n")


def print_oauth_instructions():
    """Print instructions for checking OAuth consent screen status."""
    print("\n" + "=" * 60)
    print("IMPORTANT: Check Your OAuth Consent Screen Status")
    print("=" * 60)
    print()
    print("Before authenticating, ensure your app is in PRODUCTION mode:")
    print()
    print("1. Visit: https://console.cloud.google.com/apis/credentials/consent")
    print("2. Check 'Publishing Status':")
    print("   - If 'Testing': Tokens expire after 7 days ❌")
    print("   - If 'In Production': Tokens last indefinitely ✓")
    print()
    print("3. To move to production:")
    print("   - Click 'PUBLISH APP' button")
    print("   - You may need to verify your app if prompted")
    print()
    print("4. IMPORTANT: After changing to production, re-authenticate!")
    print("   - Old tokens from 'Testing' mode will still expire")
    print("   - Generate a new token after publishing to production")
    print()
    print("=" * 60)


def main():
    """
    Run the authentication flow and create a cached token.
    """
    print("=" * 60)
    print("Google Data Portability API Authentication")
    print("=" * 60)

    # Check if client_secrets.json exists
    client_secrets_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'client_secrets.json'
    )

    if not os.path.exists(client_secrets_path):
        print("\n❌ ERROR: client_secrets.json not found!")
        print()
        print("Please follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create OAuth 2.0 credentials (Desktop app)")
        print("3. Download the credentials JSON file")
        print(f"4. Save it as: {client_secrets_path}")
        print()
        return

    print("\n✓ Client secrets found!")

    # Show OAuth consent screen instructions
    print_oauth_instructions()

    # Check existing token
    check_existing_token()

    print()
    input("Press ENTER to continue with authentication (Ctrl+C to cancel)...")
    print()

    print("Requesting access to:")
    print("  - YouTube Activity Data (myactivity.youtube)")
    print("  - Maps Activity Data (myactivity.maps)")
    print()
    print("A browser window will open for authentication...")
    print("OAuth callback will use port 8888")
    print()

    try:
        # Delete old token to force fresh authentication
        token_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'tokens',
            '.google_portability_token.pickle'
        )
        if os.path.exists(token_path):
            os.remove(token_path)
            print("✓ Removed old token file\n")

        # Create client with YouTube and Maps activity scopes
        client = get_client_local(
            scopes=['youtube_activity', 'maps_activity'],
            client_secrets_file=client_secrets_path,
            port=8888
        )

        print()
        print("=" * 60)
        print("✓ Authentication Successful!")
        print("=" * 60)
        print()
        print(f"Token cached to: {token_path}")
        print()
        print("For Airflow deployment:")
        print("1. Copy the token to your Airflow container:")
        print(f"   Local:   {token_path}")
        print(f"   Airflow: /opt/airflow/dags/tokens/.google_portability_token.pickle")
        print()
        print("2. Ensure the tokens directory is mounted in docker-compose.yml")
        print()
        print("3. Verify OAuth Consent Screen is 'In Production':")
        print("   https://console.cloud.google.com/apis/credentials/consent")
        print()
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print("✗ Authentication Failed")
        print("=" * 60)
        print(f"\nError: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()