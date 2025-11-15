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
  songs_streamed: string;
  unique_artists: string;
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
        songs_streamed,
        unique_artists,
        total_time,
        avg_daily
      FROM analytics.gold_spotify_kpis
      LIMIT 1
    `;

    const topArtistsQuery = `
      SELECT
        rank,
        name,
        plays,
        hours,
        genre
      FROM analytics.gold_spotify_top_artists
      ORDER BY rank
      LIMIT 10
    `;

    const genresQuery = `
      SELECT
        name,
        value
      FROM analytics.gold_spotify_genres
      ORDER BY rank
      LIMIT 20
    `;

    const timeSeriesQuery = `
      SELECT
        date,
        hours
      FROM analytics.gold_spotify_daily_listening
      ORDER BY date
    `;

    // Execute all queries in parallel
    const [kpis, topArtists, genres, timeSeries] = await Promise.all([
      queryClickHouseOne<SpotifyKPIs>(kpisQuery),
      queryClickHouse<TopArtist>(topArtistsQuery),
      queryClickHouse<Genre>(genresQuery),
      queryClickHouse<DailyListening>(timeSeriesQuery),
    ]);

    // Format response
    const response = {
      kpis: {
        totalTime: kpis?.total_time || '0 hrs',
        songsStreamed: kpis?.songs_streamed || '0',
        uniqueArtists: kpis?.unique_artists || '0',
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
    return NextResponse.json(
      { error: 'Failed to fetch Spotify data' },
      { status: 500 }
    );
  }
}
