/**
 * Spotify Current Track API Route (Cloudflare Workers Function)
 * Polling endpoint that returns the current playing track.
 *
 * The frontend should call this endpoint every 5–10 seconds.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
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
  device_id: string;
  device_name: string;
  device_type: string;
  device_volume_percent: number;
  context_type: string;
  context_uri: string;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const query = `SELECT * FROM gold.gold_spotify_current_track LIMIT 1`;
      const results = await queryClickHouse<ClickHouseTrackRow>(env, query);
      const row = results[0] || null;

      if (!row) {
        return {
          type: 'no_track',
          data: { is_playing: false, timestamp: new Date().toISOString() },
        };
      }

      return {
        type: 'current_track',
        data: {
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
          is_playing: row.is_playing,
          device: {
            id: row.device_id,
            name: row.device_name,
            type: row.device_type,
            volume_percent: row.device_volume_percent,
          },
          context: row.context_type ? { type: row.context_type, uri: row.context_uri } : null,
        },
      };
    },
    'spotify/current',
    request,
    {
      type: 'no_track',
      data: { is_playing: false, timestamp: new Date().toISOString() },
    }
  );

  const { body, headers } = addCacheHeaders(
    data,
    isFromCache,
    error,
    'no-cache, no-store, must-revalidate'
  );
  return Response.json(body, { headers });
}
