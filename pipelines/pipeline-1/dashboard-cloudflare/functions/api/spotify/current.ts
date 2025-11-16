/**
 * Spotify Current Track API Route (Cloudflare Workers Function)
 * Polling endpoint that returns the current playing track
 *
 * This replaces the Server-Sent Events stream from:
 * dashboard-nextjs/app/api/spotify/stream/route.ts
 *
 * Instead of maintaining a long-running Kafka consumer connection,
 * this endpoint polls the latest track from ClickHouse.
 * The frontend should call this endpoint every 5-10 seconds.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { getFallbackData } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface CurrentTrack {
  track: string;
  artist: string;
  album: string;
  album_art?: string;
  playing: boolean;
  timestamp: string;
  progress_ms?: number;
  duration_ms?: number;
}

/**
 * GET /api/spotify/current
 * Returns the most recent Spotify track from ClickHouse
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query for the most recent track
    // Assumes you have a table that stores current/recent playback state
    // Adjust the table name and columns based on your schema
    const query = `
      SELECT
        track,
        artist,
        album,
        album_art,
        playing,
        timestamp,
        progress_ms,
        duration_ms
      FROM analytics.spotify_current_track
      ORDER BY timestamp DESC
      LIMIT 1
    `;

    const results = await queryClickHouse<CurrentTrack>(env, query);
    const currentTrack = results[0] || null;

    if (!currentTrack) {
      return Response.json({
        type: 'no_track',
        data: {
          is_playing: false,
          timestamp: new Date().toISOString(),
        },
      }, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
        },
      });
    }

    return Response.json({
      type: 'current_track',
      data: currentTrack,
    }, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    });
  } catch (error) {
    console.error('Error fetching current track from ClickHouse:', error);
    console.log('Attempting to use fallback data...');

    try {
      // Try to use fallback data
      const fallbackData = await getFallbackData<any>('spotify-current');

      if (fallbackData && fallbackData.length > 0) {
        const currentTrack = fallbackData[0];

        console.log('✅ Using fallback data for current track');

        return Response.json({
          type: 'current_track',
          data: currentTrack,
          _meta: {
            cached: true,
            timestamp: new Date().toISOString(),
            note: 'ClickHouse unavailable, using cached data',
          },
        }, {
          headers: {
            'Cache-Control': 'public, max-age=300',
            'X-Data-Source': 'cache',
          },
        });
      }
    } catch (fallbackError) {
      console.error('Failed to load fallback data:', fallbackError);
    }

    // If fallback also fails, return a no-track response
    return Response.json({
      type: 'no_track',
      data: {
        is_playing: false,
        timestamp: new Date().toISOString(),
      },
      _meta: {
        cached: false,
        error: 'Unable to fetch current track data',
      },
    }, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    });
  }
}
