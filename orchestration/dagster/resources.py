"""Dagster resources — thin wrappers around `ingestion._shared.*` factories.

Resources are constructed per Definitions() init, then re-used across all
assets/schedules/sensors that depend on them. Keep them stateless beyond a
cached client handle; the underlying SDK clients (clickhouse_connect,
KafkaProducer, boto3) handle their own connection pooling.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dagster import ConfigurableResource, InitResourceContext

from ingestion._shared import clickhouse as _clickhouse_helpers
from ingestion._shared import redpanda as _redpanda_helpers
from ingestion._shared import r2 as _r2_helpers


class ClickHouseResource(ConfigurableResource):
    """Hands assets a `clickhouse_connect` Client."""

    database: Optional[str] = None

    def get_client(self) -> Any:
        return _clickhouse_helpers.get_client(database=self.database)

    def execute(self, sql: str) -> None:
        _clickhouse_helpers.execute(sql, database=self.database)

    def insert_rows(self, table: str, rows, *, column_names: list[str] | None = None) -> None:
        _clickhouse_helpers.insert_rows(
            table, rows, database=self.database, column_names=column_names
        )


class RedpandaResource(ConfigurableResource):
    """Hands assets a `KafkaProducer` wired to the in-network Redpanda broker."""

    def get_producer(self) -> Any:
        return _redpanda_helpers.get_producer()


class R2Resource(ConfigurableResource):
    """Cloudflare R2 (S3-compatible) bucket. Used for replay staging."""

    bucket: Optional[str] = None

    def get_client(self) -> Any:
        return _r2_helpers.get_client()

    def upload_bytes(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        _r2_helpers.upload_bytes(key, data, content_type=content_type)

    def download_bytes(self, key: str) -> bytes:
        return _r2_helpers.download_bytes(key)


class SpotifyResource(ConfigurableResource):
    """spotipy client backed by a CacheFileHandler. Cache file is bind-mounted
    in from the host's `tokens/` directory (read-only inside the container)."""

    # Cache file path inside the container. The host's `tokens/.spotify_cache`
    # is bind-mounted to /opt/dagster/tokens via compose.
    cache_path: str = "/opt/dagster/tokens/.spotify_cache"
    scopes: str = (
        "user-read-currently-playing "
        "user-read-playback-state "
        "user-read-recently-played "
        "user-read-private "
        "user-library-read"
    )

    _client: Any = None

    def setup_for_execution(self, context: InitResourceContext) -> None:
        # Import lazily so unit-style imports don't pull spotipy when unused.
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        from spotipy.cache_handler import CacheFileHandler

        client_id = os.environ["SPOTIFY_CLIENT_ID"]
        client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
        redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")

        cache_path = Path(self.cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cache_handler = CacheFileHandler(cache_path=str(cache_path))
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=self.scopes,
            cache_handler=cache_handler,
            open_browser=False,
        )
        # Verify the cache exists; spotipy will refresh transparently on call.
        if not cache_path.exists():
            raise RuntimeError(
                f"Spotify token cache not found at {cache_path}. "
                "Run `.venv/bin/python ingestion/spotify/authenticate_local.py` on the host first."
            )
        self._client = spotipy.Spotify(auth_manager=auth_manager)

    def get_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("SpotifyResource accessed before setup_for_execution")
        return self._client


class GoogleAuthResource(ConfigurableResource):
    """Google OAuth credentials, loaded from `auth.google_tokens`. Refreshes
    in-process and persists rotated tokens back. Filled in by Phase 4."""

    account_email: Optional[str] = None

    def get_credentials(self):  # type: ignore[no-untyped-def]
        # Import lazily — Phase 4 wires this up.
        from ingestion._shared.google_oauth import GoogleCredentials  # noqa: WPS433

        return GoogleCredentials.load_and_refresh(self.account_email)
