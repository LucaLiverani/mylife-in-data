/**
 * Spotify Data API Route (Cloudflare Workers Function)
 * Queries ClickHouse gold tables for dashboard data
 *
 * Ported from: dashboard-nextjs/app/api/spotify/data/route.ts
 */

import { queryClickHouse } from '../../_shared/clickhouse';
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

/**
 * GET /api/spotify/data
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query gold tables created by dbt
    // These are pre-aggregated and optimized for dashboard queries

    const kpisQuery = `
      SELECT
        total_plays_raw AS songs_streamed,
        unique_artists_raw AS unique_artists,
        total_time,
        avg_daily
      FROM gold.gold_spotify_kpis
      LIMIT 1
    `;

    const topArtistsQuery = `
      SELECT
        rank,
        name,
        plays,
        hours,
        genre
      FROM gold.gold_spotify_top_artists
      ORDER BY rank
      LIMIT 10
    `;

    const genresQuery = `
      SELECT
        name,
        value
      FROM gold.gold_spotify_genres
      ORDER BY rank
      LIMIT 20
    `;

    const timeSeriesQuery = `
      SELECT
        date,
        hours
      FROM gold.gold_spotify_daily_listening
      ORDER BY date
    `;

    // Execute all queries in parallel
    const [kpisResult, topArtists, genres, timeSeries] = await Promise.all([
      queryClickHouse<SpotifyKPIs>(env, kpisQuery),
      queryClickHouse<TopArtist>(env, topArtistsQuery),
      queryClickHouse<Genre>(env, genresQuery),
      queryClickHouse<DailyListening>(env, timeSeriesQuery),
    ]);

    const kpis = kpisResult[0] || null;

    // Format response - parse values to integers to remove decimals
    const response = {
      kpis: {
        totalTime: kpis?.total_time || '0 hrs',
        songsStreamed: parseInt(String(kpis?.songs_streamed || 0), 10).toString(),
        uniqueArtists: parseInt(String(kpis?.unique_artists || 0), 10).toString(),
        avgDaily: kpis?.avg_daily || '0 hrs',
      },
      topArtists: topArtists.map(artist => ({
        ...artist,
        plays: Number(artist.plays) || 0,
        hours: Number(artist.hours) || 0,
      })),
      genres: genres.map(genre => ({
        name: genre.name,
        value: Number(genre.value) || 0,
      })),
      timeSeries: {
        dates: timeSeries.map(d => d.date),
        values: timeSeries.map(d => Number(d.hours) || 0),
      },
    };

    return Response.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (error) {
    console.error('Error fetching Spotify data:', error);

    // Return empty data instead of error to allow page to load
    return Response.json({
      kpis: {
        totalTime: '0 hrs',
        songsStreamed: '0',
        uniqueArtists: '0',
        avgDaily: '0 hrs',
      },
      topArtists: [],
      genres: [],
      timeSeries: {
        dates: [],
        values: [],
      },
    });
  }
}
