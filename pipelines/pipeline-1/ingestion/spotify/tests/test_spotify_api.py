import pytest
from unittest.mock import MagicMock
import pandas as pd
from spotify_api import get_recently_played_tracks, process_tracks, create_dataframe

@pytest.fixture
def mock_spotify_client():
    """Fixture to create a mock Spotify client."""
    mock_client = MagicMock()
    mock_client.current_user_recently_played.return_value = {
        "items": [
            {
                "track": {
                    "name": "Test Track 1",
                    "artists": [{"name": "Test Artist 1"}],
                    "album": {"name": "Test Album 1", "id": "album1"},
                    "id": "track1",
                    "duration_ms": 200000,
                    "popularity": 80,
                },
                "played_at": "2025-10-14T10:00:00.000Z",
            }
        ]
    }
    return mock_client

def test_get_recently_played_tracks(mock_spotify_client):
    """Test fetching recently played tracks."""
    tracks = get_recently_played_tracks(mock_spotify_client)
    assert len(tracks) == 1
    assert tracks[0]["track"]["name"] == "Test Track 1"

def test_process_tracks():
    """Test processing of raw track data."""
    raw_tracks = [
        {
            "track": {
                "name": "Test Track 1",
                "artists": [{"name": "Test Artist 1"}],
                "album": {"name": "Test Album 1", "id": "album1"},
                "id": "track1",
                "duration_ms": 200000,
                "popularity": 80,
            },
            "played_at": "2025-10-14T10:00:00.000Z",
        }
    ]
    processed_data = process_tracks(raw_tracks)
    assert len(processed_data) == 1
    assert processed_data[0]["track_name"] == "Test Track 1"
    assert processed_data[0]["artists"] == "Test Artist 1"

def test_create_dataframe():
    """Test creation of a pandas DataFrame."""
    processed_data = [
        {
            "played_at": "2025-10-14T10:00:00.000Z",
            "track_name": "Test Track 1",
            "artists": "Test Artist 1",
            "album_name": "Test Album 1",
            "track_id": "track1",
            "album_id": "album1",
            "duration_ms": 200000,
            "popularity": 80,
        }
    ]
    df = create_dataframe(processed_data)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]["track_name"] == "Test Track 1"
