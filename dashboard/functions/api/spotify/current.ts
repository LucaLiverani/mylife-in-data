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

interface ClickHouseTrackRow {
  track_id: string;
  track_name: string;
  track_uri: string;
  album_id: string;
  album_name: string;
  album_uri: string;
  album_images: string[];
  artist_id: string;
  artist_name: string;
  artist_uri: string;
  artists_ids: string[];
  artists_names: string[];
  is_playing: boolean;
  captured_at: string;
  progress_ms: number;
  track_duration_ms: number;
  device_id: string;
  device_name: string;
  device_type: string;
  device_volume_percent: number;
  context_type: string;
  context_uri: string;
}

/**
 * GET /api/spotify/current
 * Returns the most recent Spotify track from ClickHouse
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query for the most recent track from gold view
    const query = `
      SELECT *
      FROM gold.gold_spotify_current_track
      LIMIT 1
    `;

    const results = await queryClickHouse<ClickHouseTrackRow>(env, query);
    const row = results[0] || null;

    if (!row) {
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

    // Transform to frontend format
    const currentTrack = {
      timestamp: row.captured_at,
      track_id: row.track_id,
      track_name: row.track_name,
      track_uri: row.track_uri,
      artists: row.artists_ids.map((id, idx) => ({
        id,
        name: row.artists_names[idx] || '',
        uri: `spotify:artist:${id}`,
      })),
      album: {
        id: row.album_id,
        name: row.album_name,
        uri: row.album_uri,
        images: row.album_images.map(url => ({ url, height: 0, width: 0 })),
      },
      duration_ms: row.track_duration_ms,
      progress_ms: row.progress_ms,
      is_playing: row.is_playing,
      device: {
        id: row.device_id,
        name: row.device_name,
        type: row.device_type,
        volume_percent: row.device_volume_percent,
      },
      context: row.context_type ? {
        type: row.context_type,
        uri: row.context_uri,
      } : null,
    };

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
