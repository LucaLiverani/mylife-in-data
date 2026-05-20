FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY ingestion/spotify/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /app/tokens

# Copy the spotify ingestion package preserving the import path
# (lets `from ingestion.spotify.spotify_api import ...` resolve)
COPY ingestion/ /app/ingestion/

ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep -f current_playing_producer.py || exit 1

CMD ["python", "/app/ingestion/spotify/current_playing_producer.py"]
