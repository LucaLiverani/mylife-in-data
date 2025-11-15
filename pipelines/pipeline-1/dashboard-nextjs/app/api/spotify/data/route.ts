/**
 * Spotify Data API Route
 * Queries ClickHouse gold tables for dashboard data
 */

import { NextResponse } from 'next/server';
import { queryClickHouse, queryClickHouseOne } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';
export const revalidate = 60; // Revalidate every 60 seconds

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

export async function GET() {
  try {
    // Query gold tables created by dbt
    // These are pre-aggregated and optimized for dashboard queries

    const kpisQuery = `
      SELECT
        total_plays_raw AS songs_streamed,
        unique_artists_raw AS unique_artists,
        total_time,
        avg_daily
      FROM analytics_gold.gold_spotify_kpis
      LIMIT 1
    `;

    const topArtistsQuery = `
      SELECT
        rank,
        name,
        plays,
        hours,
        genre
      FROM analytics_gold.gold_spotify_top_artists
      ORDER BY rank
      LIMIT 10
    `;

    const genresQuery = `
      SELECT
        name,
        value
      FROM analytics_gold.gold_spotify_genres
      ORDER BY rank
      LIMIT 20
    `;

    const timeSeriesQuery = `
      SELECT
        date,
        hours
      FROM analytics_gold.gold_spotify_daily_listening
      ORDER BY date
    `;

    // Execute all queries in parallel
    const [kpis, topArtists, genres, timeSeries] = await Promise.all([
      queryClickHouseOne<SpotifyKPIs>(kpisQuery),
      queryClickHouse<TopArtist>(topArtistsQuery),
      queryClickHouse<Genre>(genresQuery),
      queryClickHouse<DailyListening>(timeSeriesQuery),
    ]);

    // Format response - parse values to integers to remove decimals
    const response = {
      kpis: {
        totalTime: kpis?.total_time || '0 hrs',
        songsStreamed: parseInt(String(kpis?.songs_streamed || 0), 10).toString(),
        uniqueArtists: parseInt(String(kpis?.unique_artists || 0), 10).toString(),
        avgDaily: kpis?.avg_daily || '0 hrs',
      },
      topArtists: topArtists || [],
      genres: genres || [],
      timeSeries: {
        dates: timeSeries.map(d => d.date),
        values: timeSeries.map(d => d.hours),
      },
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('Error fetching Spotify data:', error);
    // Return empty data instead of error to allow page to load
    return NextResponse.json({
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
