import { Kafka, CompressionTypes, CompressionCodecs } from 'kafkajs';
import SnappyCodec from 'kafkajs-snappy';

export const dynamic = 'force-dynamic';

// Register Snappy compression codec
CompressionCodecs[CompressionTypes.Snappy] = SnappyCodec;

const kafka = new Kafka({
  clientId: 'spotify-dashboard-consumer',
  brokers: [process.env.KAFKA_BOOTSTRAP_SERVERS || 'localhost:9093'],
});

export async function GET() {
  const encoder = new TextEncoder();

  // Create a unique consumer for each connection
  const consumer = kafka.consumer({
    groupId: `spotify-dashboard-${Date.now()}-${Math.random().toString(36).substring(7)}`
  });

  // Track if the stream is still active
  let isActive = true;
  let keepaliveInterval: NodeJS.Timeout | null = null;

  const stream = new ReadableStream({
    async start(controller) {
      try {
        // Send initial connection message immediately
        const heartbeat = `data: ${JSON.stringify({ type: 'connected' })}\n\n`;
        controller.enqueue(encoder.encode(heartbeat));

        await consumer.connect();

        const topic = process.env.KAFKA_TOPIC || 'spotify.player.current';

        await consumer.subscribe({
          topic,
          fromBeginning: false
        });

        // Send a keepalive every 30 seconds
        keepaliveInterval = setInterval(() => {
          if (isActive) {
            try {
              const keepalive = `: keepalive\n\n`;
              controller.enqueue(encoder.encode(keepalive));
            } catch (error) {
              isActive = false;
              if (keepaliveInterval) clearInterval(keepaliveInterval);
            }
          } else {
            if (keepaliveInterval) clearInterval(keepaliveInterval);
          }
        }, 30000);

        await consumer.run({
          eachMessage: async ({ message }) => {
            // Don't process messages if stream is closed
            if (!isActive) return;

            try {
              const value = message.value?.toString();
              if (value) {
                const data = JSON.parse(value);
                // Send as Server-Sent Event only if stream is still active
                if (isActive) {
                  const sseMessage = `data: ${JSON.stringify(data)}\n\n`;
                  controller.enqueue(encoder.encode(sseMessage));
                }
              }
            } catch (error) {
              // Only log if it's not a controller closed error
              if (error instanceof Error && error.message !== 'Controller is already closed') {
                console.error('Error processing message:', error);
              }
            }
          },
        });
      } catch (error) {
        console.error('Kafka consumer error:', error);
        isActive = false;
        if (keepaliveInterval) clearInterval(keepaliveInterval);
        controller.error(error);
        try {
          await consumer.disconnect();
        } catch (disconnectError) {
          console.error('Error disconnecting consumer:', disconnectError);
        }
      }
    },

    async cancel() {
      isActive = false;
      if (keepaliveInterval) clearInterval(keepaliveInterval);
      try {
        await consumer.stop();
        await consumer.disconnect();
      } catch (error) {
        console.error('Error cleaning up consumer:', error);
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    },
  });
}
