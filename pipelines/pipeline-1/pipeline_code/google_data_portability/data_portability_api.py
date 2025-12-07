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
        """
        # Check if we have cached credentials
        if os.path.exists(self.token_cache_path):
            with open(self.token_cache_path, 'rb') as token:
                self.credentials = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Refreshing access token...")
                self.credentials.refresh(Request())
            else:
                print("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file,
                    scopes=self.scopes
                )
                self.credentials = flow.run_local_server(port=self.port)

            # Save the credentials for the next run
            os.makedirs(os.path.dirname(self.token_cache_path), exist_ok=True)
            with open(self.token_cache_path, 'wb') as token:
                pickle.dump(self.credentials, token)
                print(f"Token cached to {self.token_cache_path}")

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers with current access token."""
        if not self.credentials or not self.credentials.valid:
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

        # Add time filters if provided
        if start_time or end_time:
            time_filter = {}
            if start_time:
                time_filter['startTime'] = start_time
            if end_time:
                time_filter['endTime'] = end_time
            payload['timeFilter'] = time_filter

        response = requests.post(url, headers=self._get_headers(), json=payload)
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