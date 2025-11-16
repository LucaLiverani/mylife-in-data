/**
 * Spotify Recent Tracks API Route (Cloudflare Workers Function)
 * Returns recently played tracks
 *
 * Ported from: dashboard-nextjs/app/api/spotify/recent/route.ts
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';
import { formatDistanceToNow } from 'date-fns';

interface RecentTrack {
  track: string;
  artist: string;
  played_at: string;
  album_art: string;
}

/**
 * GET /api/spotify/recent
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query pre-aggregated gold recent tracks table
    const query = `
      SELECT
        track,
        artist,
        played_at,
        album_art
      FROM analytics_gold.gold_spotify_recent_tracks
      ORDER BY recency_rank
      LIMIT 50
    `;

    const results = await queryClickHouse<RecentTrack>(env, query);

    // Format the results with relative timestamps
    const formattedResults = results.map(track => ({
      track: track.track,
      artist: track.artist,
      time: formatDistanceToNow(new Date(track.played_at), { addSuffix: true }),
      albumArt: track.album_art || `https://picsum.photos/seed/${track.artist}/100`,
    }));

    return Response.json(formattedResults.slice(0, 10), {
      headers: {
        'Cache-Control': 'public, max-age=10',
      },
    });
  } catch (error) {
    console.error('Error fetching recent tracks:', error);

    // Return empty array instead of error to allow page to load
    return Response.json([]);
  }
}
