/**
 * Spotify Summary API Route (Cloudflare Workers Function)
 * Quick summary stats for the dashboard overview.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface SummaryStat {
  artists: string | number;
  songs: string | number;
  total_hours: string;
}

interface SummaryResponse {
  stats: { label: string; value: string }[];
  totalHours: string;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<SummaryResponse>(
    async () => {
      const query = `SELECT * FROM gold.gold_spotify_kpis_summary LIMIT 1`;
      const results = await queryClickHouse<SummaryStat>(env, query);
      const result = results[0] || null;

      const artists = parseInt(String(result?.artists || 0), 10);
      const songs = parseInt(String(result?.songs || 0), 10);

      return {
        stats: [
          { label: 'Artists', value: artists.toString() },
          { label: 'Songs', value: songs.toString() },
        ],
        totalHours: result?.total_hours || '0 hrs',
      };
    },
    'spotify/summary',
    request,
    {
      stats: [
        { label: 'Artists', value: '0' },
        { label: 'Songs', value: '0' },
      ],
      totalHours: '0 hrs',
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);
  return Response.json(body, { headers });
}
