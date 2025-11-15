/**
 * Spotify Summary API Route
 * Quick summary stats for the dashboard overview
 */

import { NextResponse } from 'next/server';
import { queryClickHouseOne } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';
export const revalidate = 60;

interface SummaryStat {
  artists: string | number;
  songs: string | number;
  total_hours: string;
}

export async function GET() {
  try {
    // Query pre-aggregated gold KPIs table - use raw values for integers
    const query = `
      SELECT
        unique_artists_raw AS artists,
        total_plays_raw AS songs,
        total_time AS total_hours
      FROM analytics_gold.gold_spotify_kpis
      LIMIT 1
    `;

    const result = await queryClickHouseOne<SummaryStat>(query);

    // Parse the values to integers, removing any decimals
    const artists = parseInt(String(result?.artists || 0), 10);
    const songs = parseInt(String(result?.songs || 0), 10);

    return NextResponse.json({
      stats: [
        { label: 'Artists', value: artists.toString() },
        { label: 'Songs', value: songs.toString() },
      ],
      totalHours: result?.total_hours || '0 hrs',
    });
  } catch (error) {
    console.error('Error fetching Spotify summary:', error);
    // Return empty data instead of error to allow page to load
    return NextResponse.json({
      stats: [
        { label: 'Artists', value: '0' },
        { label: 'Songs', value: '0' },
      ],
      totalHours: '0 hrs',
    });
  }
}
