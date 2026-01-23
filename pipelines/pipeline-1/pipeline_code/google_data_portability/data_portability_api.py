"""
Google Data Portability API client for exporting YouTube, Maps, and other Google data.

This module provides a Python interface to the Google Data Portability API,
allowing you to programmatically export your behavioral data from Google services.
"""

import os
import time
import json
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle


class DataPortabilityClient:
    """
    Client for interacting with the Google Data Portability API.

    Similar to the Spotify client, this handles OAuth authentication,
    token management, and API calls to export data from Google services.
    """

    # API endpoint base URL
    API_BASE_URL = "https://dataportability.googleapis.com/v1"

    # Available resource scopes for different Google services
    AVAILABLE_SCOPES = {
        # YouTube scopes
        'youtube_activity': 'https://www.googleapis.com/auth/dataportability.myactivity.youtube',
        'youtube_channel': 'https://www.googleapis.com/auth/dataportability.youtube.channel',
        'youtube_comments': 'https://www.googleapis.com/auth/dataportability.youtube.comments',
        'youtube_subscriptions': 'https://www.googleapis.com/auth/dataportability.youtube.subscriptions',
        'youtube_playlists': 'https://www.googleapis.com/auth/dataportability.youtube.public_playlists',
        'youtube_music': 'https://www.googleapis.com/auth/dataportability.youtube.music',

        # Maps scopes
        'maps_activity': 'https://www.googleapis.com/auth/dataportability.myactivity.maps',
        'maps_starred_places': 'https://www.googleapis.com/auth/dataportability.maps.starred_places',
        'maps_reviews': 'https://www.googleapis.com/auth/dataportability.maps.reviews',
        'maps_commute_routes': 'https://www.googleapis.com/auth/dataportability.maps.commute_routes',
        'maps_photos': 'https://www.googleapis.com/auth/dataportability.maps.photos',

        # Search scope
        'search_activity': 'https://www.googleapis.com/auth/dataportability.myactivity.search',

        # Chrome scope
        'chrome_history': 'https://www.googleapis.com/auth/dataportability.chrome.history',

        # Shopping scope
        'shopping_activity': 'https://www.googleapis.com/auth/dataportability.myactivity.shopping',
    }

    def __init__(
        self,
        client_secrets_file: str,
        token_cache_path: str = 'tokens/.google_portability_token.pickle',
        scopes: Optional[List[str]] = None,
        port: int = 8888
    ):
        """
        Initialize the Data Portability API client.

        Args:
            client_secrets_file: Path to the OAuth client secrets JSON file
            token_cache_path: Path to store the token cache
            scopes: List of scope keys from AVAILABLE_SCOPES to request access to
            port: Port for OAuth callback server (default: 8888)
        """
        self.client_secrets_file = client_secrets_file
        self.token_cache_path = token_cache_path
        self.port = port

        # Default to YouTube and Maps activity if no scopes specified
        if scopes is None:
            scopes = ['youtube_activity', 'maps_activity']

        # Convert scope keys to full scope URLs
        self.scopes = [self.AVAILABLE_SCOPES[scope] for scope in scopes]

        self.credentials = None
        self._authenticate()

    def _authenticate(self):
        """
        Handle OAuth authentication flow with token caching.
        Similar to Spotify's token management.

        Improved to handle token rotation and persistence issues.
        """
        # Check if we have cached credentials
        if os.path.exists(self.token_cache_path):
            print(f"Loading cached token from {self.token_cache_path}")
            with open(self.token_cache_path, 'rb') as token:
                self.credentials = pickle.load(token)

            # Log token info for debugging (without exposing sensitive data)
            if self.credentials:
                has_refresh = bool(self.credentials.refresh_token)
                is_valid = self.credentials.valid
                is_expired = self.credentials.expired if hasattr(self.credentials, 'expired') else False
                print(f"Token state: valid={is_valid}, expired={is_expired}, has_refresh_token={has_refresh}")

        # If there are no (valid) credentials available, let the user log in
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Access token expired. Refreshing...")

                # Store the old refresh token to detect rotation
                old_refresh_token = self.credentials.refresh_token

                try:
                    # Attempt to refresh the token
                    self.credentials.refresh(Request())

                    # Check if refresh token was rotated (Google sometimes does this)
                    new_refresh_token = self.credentials.refresh_token
                    if new_refresh_token != old_refresh_token:
                        print("Refresh token was rotated by Google")

                    # CRITICAL: Save the refreshed credentials immediately
                    # This is essential because Google may rotate the refresh token
                    self._save_credentials()
                    print(f"✓ Token refreshed and saved to {self.token_cache_path}")

                except Exception as refresh_error:
                    # Token refresh failed - this is often due to:
                    # 1. OAuth consent screen in "Testing" mode (tokens expire after 7 days)
                    # 2. Refresh token revoked by user
                    # 3. Scope changes

                    error_msg = (
                        f"Token refresh failed: {refresh_error}\n\n"
                        "Common causes:\n"
                        "1. OAuth Consent Screen in 'Testing' mode (tokens expire after 7 days)\n"
                        "   - Go to: https://console.cloud.google.com/apis/credentials/consent\n"
                        "   - Change Publishing Status to 'In Production'\n"
                        "   - Then re-authenticate (tokens last indefinitely in production)\n\n"
                        "2. Refresh token was revoked\n"
                        "   - Check: https://myaccount.google.com/permissions\n\n"
                        "3. Token file may not be writable in this environment\n\n"
                        "To fix:\n"
                        "1. Run locally: python google_data_portability/authenticate.py\n"
                        "2. This will open a browser for re-authentication\n"
                        "3. Copy the new token to Airflow:\n"
                        f"   - Local: {self.token_cache_path}\n"
                        f"   - Airflow: /opt/airflow/dags/tokens/.google_portability_token.pickle\n"
                        "4. Verify OAuth consent screen is in 'Production' mode\n"
                    )
                    raise Exception(error_msg)
            else:
                # No valid credentials and no refresh token
                # Check if we're in a non-interactive environment
                is_interactive = os.isatty(0)
                if not is_interactive:
                    error_msg = (
                        "No valid authentication token found.\n\n"
                        "Cannot run interactive OAuth flow in non-interactive environment (e.g., Airflow).\n\n"
                        "To fix this:\n"
                        "1. Verify OAuth consent screen is in 'Production' mode:\n"
                        "   - Go to: https://console.cloud.google.com/apis/credentials/consent\n"
                        "   - Publishing Status should be 'In Production' (not 'Testing')\n\n"
                        "2. Run locally: python google_data_portability/authenticate.py\n"
                        "3. This will open a browser for authentication\n"
                        "4. Copy the generated token to Airflow:\n"
                        f"   - Local: {self.token_cache_path}\n"
                        f"   - Airflow: /opt/airflow/dags/tokens/.google_portability_token.pickle\n"
                    )
                    raise Exception(error_msg)

                print("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file,
                    scopes=self.scopes
                )
                self.credentials = flow.run_local_server(port=self.port)

                # Save the credentials for the next run
                self._save_credentials()
                print(f"✓ Token cached to {self.token_cache_path}")

    def _save_credentials(self):
        """
        Save credentials to the token cache file.
        Separated into its own method for better error handling and reusability.
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.token_cache_path), exist_ok=True)

            # Write to a temporary file first, then atomic rename
            # This prevents corruption if the process is interrupted
            temp_path = f"{self.token_cache_path}.tmp"
            with open(temp_path, 'wb') as token:
                pickle.dump(self.credentials, token)

            # Atomic rename (on POSIX systems)
            os.replace(temp_path, self.token_cache_path)

            # Verify the file was written correctly
            if os.path.exists(self.token_cache_path):
                file_size = os.path.getsize(self.token_cache_path)
                print(f"Credentials saved successfully ({file_size} bytes)")
            else:
                print("WARNING: Token file not found after save attempt!")

        except Exception as e:
            print(f"ERROR saving credentials: {e}")
            print(f"Token path: {self.token_cache_path}")
            print(f"Directory writable: {os.access(os.path.dirname(self.token_cache_path), os.W_OK)}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """
        Get authorization headers with current access token.
        Automatically refreshes token if expired.
        """
        # Check if token needs refresh
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Token expired, refreshing before API call...")
                old_refresh_token = self.credentials.refresh_token

                try:
                    self.credentials.refresh(Request())

                    # Save if refresh token was rotated
                    new_refresh_token = self.credentials.refresh_token
                    if new_refresh_token != old_refresh_token:
                        print("Refresh token was rotated during API call")
                        self._save_credentials()

                except Exception as e:
                    print(f"Token refresh failed in _get_headers: {e}")
                    # Re-authenticate from scratch
                    self._authenticate()
            else:
                # No valid credentials at all
                self._authenticate()

        return {
            'Authorization': f'Bearer {self.credentials.token}',
            'Content-Type': 'application/json'
        }

    def initiate_archive(
        self,
        resources: List[str],
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict:
        """
        Initiate a data portability archive export job.

        Args:
            resources: List of resource groups to export (e.g., ['myactivity.youtube', 'myactivity.maps'])
            start_time: Optional ISO 8601 timestamp for filtering data (e.g., '2023-01-01T00:00:00Z')
            end_time: Optional ISO 8601 timestamp for filtering data (e.g., '2024-01-01T00:00:00Z')

        Returns:
            Dict containing archiveJobId and other response data
        """
        url = f"{self.API_BASE_URL}/portabilityArchive:initiate"

        payload = {"resources": resources}

        # Add time filters if provided (top-level parameters, not nested)
        if start_time:
            payload['startTime'] = start_time
        if end_time:
            payload['endTime'] = end_time

        response = requests.post(url, headers=self._get_headers(), json=payload)

        # Better error handling to capture Google's error details
        if not response.ok:
            error_details = response.text
            try:
                error_json = response.json()
                error_details = json.dumps(error_json, indent=2)
            except:
                pass
            print(f"API Error Response ({response.status_code}): {error_details}")
            response.raise_for_status()

        result = response.json()
        print(f"Archive job initiated: {result.get('archiveJobId')}")
        return result

    def get_archive_state(self, archive_job_id: str) -> Dict:
        """
        Check the status of an archive export job.

        Args:
            archive_job_id: The job ID returned from initiate_archive()

        Returns:
            Dict containing job state and download URLs when ready
        """
        url = f"{self.API_BASE_URL}/archiveJobs/{archive_job_id}/portabilityArchiveState"

        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()

        return response.json()

    def wait_for_archive(
        self,
        archive_job_id: str,
        poll_interval: int = 30,
        max_wait_time: int = 3600
    ) -> Tuple[Dict, List[str]]:
        """
        Poll the archive job until it's complete and return download URLs.

        Args:
            archive_job_id: The job ID to monitor
            poll_interval: Seconds between status checks (default: 30)
            max_wait_time: Maximum seconds to wait (default: 3600 = 1 hour)

        Returns:
            Tuple of (job_state_dict, list_of_download_urls)
        """
        start_time = time.time()

        while True:
            state = self.get_archive_state(archive_job_id)
            job_state = state.get('state', 'UNKNOWN')

            print(f"Job {archive_job_id}: {job_state}")

            if job_state == 'COMPLETE':
                urls = state.get('urls', [])
                print(f"Archive complete! {len(urls)} file(s) ready for download")
                return state, urls

            elif job_state == 'FAILED':
                raise Exception(f"Archive job failed: {state}")

            elif job_state in ['IN_PROGRESS', 'INITIATED']:
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    raise TimeoutError(f"Archive job did not complete within {max_wait_time} seconds")

                print(f"Waiting {poll_interval}s... (elapsed: {int(elapsed)}s)")
                time.sleep(poll_interval)

            else:
                raise Exception(f"Unknown job state: {job_state}")

    def download_archive_file(self, url: str, output_path: str):
        """
        Download an archive file from the signed URL.

        Args:
            url: The signed download URL from the archive response
            output_path: Local path to save the downloaded file
        """
        print(f"Downloading to {output_path}...")

        # Signed URLs don't need authorization headers
        response = requests.get(url, stream=True)
        response.raise_for_status()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Downloaded: {output_path}")

    def reset_authorization(self):
        """
        Reset authorization to allow re-exporting the same resources.
        """
        url = f"{self.API_BASE_URL}/authorization:reset"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        print("Authorization reset successfully")
        return response.json()


def get_client_local(
    scopes: Optional[List[str]] = None,
    client_secrets_file: str = 'client_secrets.json',
    token_cache_path: str = 'tokens/.google_portability_token.pickle',
    port: int = 8888
) -> DataPortabilityClient:
    """
    Get a Data Portability API client for local development.

    Args:
        scopes: List of scope keys to request (e.g., ['youtube_activity', 'maps_activity'])
        client_secrets_file: Path to OAuth client secrets file
        token_cache_path: Path to store the token cache
        port: Port for OAuth callback server (default: 8888)

    Returns:
        Authenticated DataPortabilityClient instance
    """
    return DataPortabilityClient(
        client_secrets_file=client_secrets_file,
        token_cache_path=token_cache_path,
        scopes=scopes,
        port=port
    )