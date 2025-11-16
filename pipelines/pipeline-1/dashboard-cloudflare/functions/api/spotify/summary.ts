/**
 * Spotify Summary API Route (Cloudflare Workers Function)
 * Quick summary stats for the dashboard overview
 *
 * Ported from: dashboard-nextjs/app/api/spotify/summary/route.ts
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';

interface SummaryStat {
  artists: string | number;
  songs: string | number;
  total_hours: string;
}

/**
 * GET /api/spotify/summary
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query pre-aggregated gold KPIs table - use raw values for integers
    const query = `
      SELECT
        unique_artists AS artists,
        total_plays_raw AS songs,
        total_time AS total_hours
      FROM analytics_gold.gold_spotify_kpis
      LIMIT 1
    `;

    const results = await queryClickHouse<SummaryStat>(env, query);
    const result = results[0] || null;

    // Parse the values to integers, removing any decimals
    const artists = parseInt(String(result?.artists || 0), 10);
    const songs = parseInt(String(result?.songs || 0), 10);

    return Response.json({
      stats: [
        { label: 'Artists', value: artists.toString() },
        { label: 'Songs', value: songs.toString() },
      ],
      totalHours: result?.total_hours || '0 hrs',
    }, {
      headers: {
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (error) {
    console.error('Error fetching Spotify summary:', error);

    // Return empty data instead of error to allow page to load
    return Response.json({
      stats: [
        { label: 'Artists', value: '0' },
        { label: 'Songs', value: '0' },
      ],
      totalHours: '0 hrs',
    });
  }
}
