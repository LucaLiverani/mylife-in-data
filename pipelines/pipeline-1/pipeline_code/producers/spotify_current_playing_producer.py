import time
import json
import logging
import os
import signal
import sys
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spotify.spotify_api import get_spotify_producer_client, get_currently_playing 


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('spotify_producer.log')
    ]
)

log = logging.getLogger(__name__)

# Configuration
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 1))
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'spotify.player.current')
MAX_RETRIES = 3
RETRY_BACKOFF = 5

class SpotifyCurrentPlayingProducer:
    """Producer for currently playing Spotify track"""
    
    def __init__(self):
        self.sp = None
        self.producer = None
        self.running = False
        self.last_state_fingerprint = None
        self.consecutive_errors = 0
        
    def setup(self):
        """Initialize Spotify client and Kafka producer"""
        log.info("Setting up Spotify producer...")
        
        # Spotify client - Use producer-specific client
        try:
            self.sp = get_spotify_producer_client()
            log.info("Spotify client authenticated")
        except FileNotFoundError as e:
            log.error(f"Token cache not found: {e}")
            log.error("Please run: python scripts/authenticate_spotify.py")
            raise
        except Exception as e:
            log.error(f"Failed to authenticate Spotify: {e}")
            raise
        
        # Kafka producer
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                compression_type='snappy',
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            log.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP}")
        except Exception as e:
            log.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def _get_state_fingerprint(self, current_playback):
        """Generates a simple tuple representing the current playback state."""
        if not current_playback or not current_playback.get('item'):
            return (None, False) # No track, not playing
        
        track_id = current_playback['item'].get('id')
        is_playing = current_playback.get('is_playing', False)
        return (track_id, is_playing)

    def poll_and_publish(self):
        """Poll Spotify and publish current track to Kafka only if state changes."""
        try:
            current = get_currently_playing(self.sp)
            current_state_fingerprint = self._get_state_fingerprint(current)

            if current_state_fingerprint == self.last_state_fingerprint:
                # No change in state, do nothing
                return

            # State has changed, prepare and send message
            log_message = ""
            if current is None:
                message = { 'timestamp': datetime.utcnow().isoformat() + 'Z', 'is_playing': False, 'track_id': None }
                log_message = "Playback stopped or unavailable."
            else:
                item = current.get('item', {})
                track_id = item.get('id')
                is_playing = current.get('is_playing', False)
                
                if self.last_state_fingerprint is None:
                    log_message = "Producer started."
                elif track_id != self.last_state_fingerprint[0]:
                    artist_names = ', '.join([a.get('name', 'N/A') for a in item.get('artists', [])])
                    log_message = f"New track: {item.get('name')} - {artist_names}"
                elif is_playing != self.last_state_fingerprint[1]:
                    log_message = f"Playback {'resumed' if is_playing else 'paused'}."

                message = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'track_id': track_id,
                    'track_name': item.get('name'),
                    'track_uri': item.get('uri'),
                    'artists': [
                        {'id': artist.get('id'), 'name': artist.get('name'), 'uri': artist.get('uri')}
                        for artist in item.get('artists', [])
                    ],
                    'album': {
                        'id': item.get('album', {}).get('id'),
                        'name': item.get('album', {}).get('name'),
                        'uri': item.get('album', {}).get('uri'),
                        'images': item.get('album', {}).get('images', []),
                    },
                    'duration_ms': item.get('duration_ms'),
                    'progress_ms': current.get('progress_ms'),
                    'is_playing': is_playing,
                    'device': {
                        'id': current.get('device', {}).get('id'),
                        'name': current.get('device', {}).get('name'),
                        'type': current.get('device', {}).get('type'),
                        'volume_percent': current.get('device', {}).get('volume_percent'),
                    },
                    'context': current.get('context'),
                }

            log.info(f"State change detected: {log_message} Sending to Kafka.")
            future = self.producer.send(KAFKA_TOPIC, value=message, key=message.get('track_id'))
            future.get(timeout=10) # Wait for send confirmation

            # Update state
            self.last_state_fingerprint = current_state_fingerprint
            self.consecutive_errors = 0

        except KafkaError as e:
            self.consecutive_errors += 1
            log.error(f"Kafka error: {e}")
            if self.consecutive_errors >= MAX_RETRIES:
                log.error("Too many consecutive Kafka errors, reconnecting...")
                self.reconnect_kafka()
        
        except Exception as e:
            self.consecutive_errors += 1
            log.error(f"Error polling Spotify: {e}", exc_info=True)
            
            if self.consecutive_errors >= MAX_RETRIES:
                log.error("Too many consecutive errors, will retry after backoff...")
                time.sleep(RETRY_BACKOFF)
                self.consecutive_errors = 0
    
    def reconnect_kafka(self):
        """Reconnect to Kafka"""
        try:
            if self.producer:
                self.producer.close()
            
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                compression_type='snappy',
                acks='all',
                retries=3,
            )
            
            self.consecutive_errors = 0
            log.info("Reconnected to Kafka")
            
        except Exception as e:
            log.error(f"Failed to reconnect to Kafka: {e}")
    
    def run(self):
        """Main loop"""
        log.info("="*60)
        log.info("Spotify Currently Playing Producer")
        log.info("="*60)
        log.info(f"Kafka: {KAFKA_BOOTSTRAP}")
        log.info(f"Topic: {KAFKA_TOPIC}")
        log.info(f"Poll Interval: {POLL_INTERVAL} seconds")
        log.info("="*60)
        
        self.setup()
        self.running = True
        
        try:
            while self.running:
                self.poll_and_publish()
                time.sleep(POLL_INTERVAL)
        
        except KeyboardInterrupt:
            log.info("\nReceived shutdown signal")
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        log.info("Shutting down producer...")
        self.running = False
        
        if self.producer:
            self.producer.flush()
            self.producer.close()
            log.info("Kafka producer closed")
        
        log.info("Goodbye")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    log.info(f"\nReceived signal {signum}")
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run producer
    producer = SpotifyCurrentPlayingProducer()
    producer.run()