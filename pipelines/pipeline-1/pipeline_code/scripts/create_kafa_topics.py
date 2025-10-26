# scripts/create_kafka_topics.py
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def create_topics():
    """Create Kafka topics for Spotify data pipeline"""
    
    # Connect to Kafka
    admin_client = KafkaAdminClient(
        bootstrap_servers='localhost:9093',
        client_id='topic-creator'
    )
    
    # Define topics
    topics = [
        NewTopic(
            name='spotify.tracks.raw',
            num_partitions=3,
            replication_factor=1,
            topic_configs={
                'compression.type': 'snappy',
                'retention.ms': '604800000',  # 7 days
                'cleanup.policy': 'delete',
                'max.message.bytes': '10485760',  # 10MB
            }
        ),
        NewTopic(
            name='spotify.player.current',
            num_partitions=3,
            replication_factor=1,
            topic_configs={
                'compression.type': 'snappy',
                'retention.ms': '604800000',  # 7 days
                'cleanup.policy': 'delete',
                'max.message.bytes': '10485760',  # 10MB
            }                     
        ),
    ]
    
    # Create topics
    try:
        result = admin_client.create_topics(
            new_topics=topics,
            validate_only=False
        )
        
        for topic, future in result.items():
            try:
                future.result()  # Block until topic is created
                log.info(f"Topic '{topic}' created successfully")
            except TopicAlreadyExistsError:
                log.warning(f"Topic '{topic}' already exists")
            except Exception as e:
                log.error(f"Failed to create topic '{topic}': {e}")
                
    except Exception as e:
        log.error(f"Failed to create topics: {e}")
    finally:
        admin_client.close()

if __name__ == '__main__':
    create_topics()