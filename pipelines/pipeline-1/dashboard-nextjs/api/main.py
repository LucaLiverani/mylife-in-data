"""
FastAPI backend for MyLife in Data Dashboard
Serves data endpoints for the Next.js frontend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict

app = FastAPI(title="MyLife in Data API")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= HELPER FUNCTIONS =============

def generate_dates(days: int = 365):
    """Generate date range"""
    end_date = datetime.now()
    return pd.date_range(end=end_date, periods=days, freq='D')


# ============= SPOTIFY ENDPOINTS =============

@app.get("/api/spotify/summary")
async def get_spotify_summary():
    """Get Spotify summary data"""
    return {
        "stats": [
            {"label": "Artists", "value": "247"},
            {"label": "Songs", "value": "15,847"}
        ],
        "totalHours": "1,234 hrs"
    }


@app.get("/api/spotify/data")
async def get_spotify_data():
    """Get complete Spotify analytics"""
    dates = generate_dates(365)

    # Mock data
    artists = [
        {"rank": 1, "name": "The Weeknd", "plays": 1247, "hours": 42.4, "genre": "Pop, R&B"},
        {"rank": 2, "name": "Dua Lipa", "plays": 987, "hours": 33.6, "genre": "Pop, Dance"},
        {"rank": 3, "name": "Tame Impala", "plays": 856, "hours": 29.1, "genre": "Psychedelic Rock"},
        {"rank": 4, "name": "Billie Eilish", "plays": 743, "hours": 25.3, "genre": "Alternative Pop"},
        {"rank": 5, "name": "Arctic Monkeys", "plays": 692, "hours": 23.5, "genre": "Indie Rock"},
    ]

    genres = [
        {"name": "Pop", "value": 35},
        {"name": "Electronic", "value": 25},
        {"name": "Indie", "value": 20},
        {"name": "Rock", "value": 15},
        {"name": "Hip Hop", "value": 5}
    ]

    # Time series data
    listening_hours = np.random.normal(3.4, 1.2, len(dates)).clip(0, 8).tolist()

    return {
        "kpis": {
            "totalTime": "1,234 hrs",
            "songsStreamed": "15,847",
            "uniqueArtists": "247",
            "avgDaily": "3.4 hrs"
        },
        "topArtists": artists,
        "genres": genres,
        "timeSeries": {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "values": listening_hours
        }
    }


@app.get("/api/spotify/recent")
async def get_recent_tracks():
    """Get recently played tracks"""
    return [
        {"track": "One More Time", "artist": "Daft Punk", "time": "2 min ago", "albumArt": "https://picsum.photos/seed/daftpunk/100"},
        {"track": "The Less I Know", "artist": "Tame Impala", "time": "15 min ago", "albumArt": "https://picsum.photos/seed/tameimpala/100"},
        {"track": "Do I Wanna Know", "artist": "Arctic Monkeys", "time": "1 hour ago", "albumArt": "https://picsum.photos/seed/arcticmonkeys/100"},
        {"track": "Creep", "artist": "Radiohead", "time": "2 hours ago", "albumArt": "https://picsum.photos/seed/radiohead/100"},
        {"track": "Last Nite", "artist": "The Strokes", "time": "3 hours ago", "albumArt": "https://picsum.photos/seed/thestrokes/100"},
        {"track": "Electric Feel", "artist": "MGMT", "time": "4 hours ago", "albumArt": "https://picsum.photos/seed/mgmt/100"},
        {"track": "1901", "artist": "Phoenix", "time": "5 hours ago", "albumArt": "https://picsum.photos/seed/phoenix/100"}
    ]


# ============= TRAVEL ENDPOINTS =============

@app.get("/api/travel/data")
async def get_travel_data():
    """Get travel and location data"""
    locations = [
        {"name": "Tokyo, Japan", "lat": 35.6762, "lng": 139.6503, "date": "2024-11-15", "duration": "7 days"},
        {"name": "Paris, France", "lat": 48.8566, "lng": 2.3522, "date": "2024-10-20", "duration": "5 days"},
        {"name": "New York, USA", "lat": 40.7128, "lng": -74.0060, "date": "2024-09-10", "duration": "4 days"},
        {"name": "London, UK", "lat": 51.5074, "lng": -0.1278, "date": "2024-08-15", "duration": "6 days"},
        {"name": "Barcelona, Spain", "lat": 41.3851, "lng": 2.1734, "date": "2024-07-22", "duration": "8 days"},
    ]

    return {
        "locations": locations,
        "stats": {
            "totalDistance": "45,678 mi",
            "countries": "12",
            "cities": "23",
            "longestTrip": "14 days"
        }
    }


# ============= OVERVIEW ENDPOINTS =============

@app.get("/api/overview/stats")
async def get_overview_stats():
    """Get overall dashboard statistics"""
    dates = generate_dates(30)

    # Data generation stats
    spotify_data = np.random.randint(200, 400, size=30).tolist()
    youtube_data = np.random.randint(150, 350, size=30).tolist()
    google_data = np.random.randint(300, 500, size=30).tolist()
    maps_data = np.random.randint(50, 150, size=30).tolist()

    return {
        "summary": {
            "songsStreamed": "15,847",
            "videosWatched": "3,456",
            "searchQueries": "12,847",
            "citiesVisited": "23"
        },
        "dataGeneration": {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "spotify": spotify_data,
            "youtube": youtube_data,
            "google": google_data,
            "maps": maps_data,
            "totalEvents": f"{int(np.sum([spotify_data[-1], youtube_data[-1], google_data[-1], maps_data[-1]]) * 30):,}",
            "avgPerDay": f"{int(np.mean(np.array(spotify_data) + np.array(youtube_data) + np.array(google_data) + np.array(maps_data))):,}"
        }
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "MyLife in Data API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)