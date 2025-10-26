# Spotify Currently Playing Producer

This directory contains a standalone Kafka producer that monitors a user's Spotify activity and streams playback events to a Kafka topic.

## How it Works

The producer is a Python script designed to run continuously in a Docker container. It operates in a stateful manner to ensure efficiency and minimize redundant messages.

1.  **Polling**: The script polls the Spotify API at a regular interval (configurable, e.g., every 1 second) to get the user's current playback state.
2.  **State Management**: It maintains the last known playback state in memory (specifically, the track ID and the `is_playing` status).
3.  **Change Detection**: On each poll, it compares the current state to the last known state.
4.  **Event Publishing**: A JSON message is published to the `spotify.player.current` Kafka topic **only if a change is detected**. This includes events like:
    *   A new song starts playing.
    *   The user pauses or resumes playback.
    *   Playback stops entirely.

This stateful approach avoids flooding the Kafka topic with thousands of identical messages while a song is playing, ensuring that only meaningful events are captured.

## How to Run

The producer requires a one-time authentication step to grant it access to the Spotify API.

### 1. Authenticate

Run the authentication script from the `pipeline_code` directory. This will open a browser window for you to log in and approve the permissions.

```bash
# from ./pipeline_code
python scripts/authenticate_spotify.py
```

This creates a token cache file in `./pipeline_code/tokens/` which will be mounted into the producer's container.

### 2. Run the Producer

Once authenticated, you can build and run the producer using Docker Compose from the `producers` directory.

```bash
# from ./pipeline_code/producers
docker-compose up --build -d
```

### 3. Verify

You can monitor the producer's logs to see the events it's publishing.

```bash
docker logs -f spotify-current-producer
```
