/**
 * Spotify Recent Tracks API Route (Cloudflare Workers Function)
 * Returns recently played tracks as a flat array.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface RecentTrack {
  track: string;
  artist: string;
  played_at: string;
  album_art: string;
  relative_time: string;
}

interface FormattedRecent {
  track: string;
  artist: string;
  time: string;
  relativeTime: string;
  albumArt: string;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<FormattedRecent[]>(
    async () => {
      const query = `SELECT * FROM gold.gold_spotify_recent_tracks LIMIT 50`;
      const results = await queryClickHouse<RecentTrack>(env, query);

      return results
        .map(track => ({
          track: track.track,
          artist: track.artist,
          time: track.played_at,
          relativeTime: track.relative_time,
          albumArt: track.album_art || `https://picsum.photos/seed/${track.artist}/100`,
        }))
        .slice(0, 10);
    },
    'spotify/recent',
    request,
    [] // empty array as last-resort fallback
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error, 'public, max-age=10');
  return Response.json(body, { headers });
}
