/**
 * Spotify Data API Route (Cloudflare Workers Function)
 * Aggregated data for the Spotify dashboard page.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface SpotifyKPIs {
  total_time: string;
  songs_streamed: string | number;
  unique_artists: string | number;
  avg_daily: string;
}

interface TopArtist {
  rank: number;
  name: string;
  plays: number;
  hours: number;
  genre: string;
}

interface Genre {
  name: string;
  value: number;
}

interface DailyListening {
  date: string;
  hours: number;
}

interface SpotifyDataResponse {
  kpis: {
    totalTime: string;
    songsStreamed: string;
    uniqueArtists: string;
    avgDaily: string;
  };
  topArtists: TopArtist[];
  genres: Genre[];
  timeSeries: { dates: string[]; values: number[] };
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<SpotifyDataResponse>(
    async () => {
      const [kpisResult, topArtists, genres, timeSeries] = await Promise.all([
        queryClickHouse<SpotifyKPIs>(env, `SELECT * FROM gold.gold_spotify_kpis_dashboard LIMIT 1`),
        queryClickHouse<TopArtist>(env, `SELECT * FROM gold.gold_spotify_top_artists LIMIT 10`),
        queryClickHouse<Genre>(env, `SELECT * FROM gold.gold_spotify_genres LIMIT 20`),
        queryClickHouse<DailyListening>(env, `SELECT * FROM gold.gold_spotify_daily_listening ORDER BY date ASC`),
      ]);

      const kpis = kpisResult[0] || null;

      return {
        kpis: {
          totalTime: kpis?.total_time || '0 hrs',
          songsStreamed: parseInt(String(kpis?.songs_streamed || 0), 10).toString(),
          uniqueArtists: parseInt(String(kpis?.unique_artists || 0), 10).toString(),
          avgDaily: kpis?.avg_daily || '0 hrs',
        },
        topArtists: topArtists.map(a => ({
          ...a,
          plays: Number(a.plays) || 0,
          hours: Number(a.hours) || 0,
        })),
        genres: genres.map(g => ({ name: g.name, value: Number(g.value) || 0 })),
        timeSeries: {
          dates: timeSeries.map(d => d.date),
          values: timeSeries.map(d => Number(d.hours) || 0),
        },
      };
    },
    'spotify/data',
    request,
    {
      kpis: { totalTime: '0 hrs', songsStreamed: '0', uniqueArtists: '0', avgDaily: '0 hrs' },
      topArtists: [],
      genres: [],
      timeSeries: { dates: [], values: [] },
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);
  return Response.json(body, { headers });
}
