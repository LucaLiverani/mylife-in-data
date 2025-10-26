FROM python:3.11-slim

# Set working directory
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

COPY producers/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN mkdir -p /app/tokens

COPY spotify/ /app/spotify/
COPY producers/ /app/producers/

ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep -f spotify_current_playing_producer.py || exit 1

# Run the producer
CMD ["python", "/app/producers/spotify_current_playing_producer.py"]