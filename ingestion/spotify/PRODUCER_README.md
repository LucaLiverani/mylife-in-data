# Spotify Currently Playing Producer

Standalone Kafka producer that monitors Spotify playback and streams events to the `spotify.player.current` topic.

## How it works

A Python script polls the Spotify API every ~1s, tracks the last known state in memory, and publishes a JSON message **only when something changes** (new track, pause, resume, stop). Avoids flooding Kafka with thousands of identical "still playing track X" messages.

## How to run

### 1. Authenticate (one-time)

From the repo root:

```bash
python ingestion/spotify/authenticate_local.py
```

This opens a browser, you approve, and a token cache is written to `tokens/.spotify_cache` at the repo root.

### 2. Run the producer

```bash
(cd ingestion/spotify && docker compose up --build -d)
```

### 3. Verify

```bash
docker logs -f spotify-current-producer
```
