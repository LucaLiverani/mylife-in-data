/**
 * Spotify Summary API Route
 * Quick summary stats for the dashboard overview
 */

import { NextResponse } from 'next/server';
import { queryClickHouseOne } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';
export const revalidate = 60;

interface SummaryStat {
  artists: string;
  songs: string;
  total_hours: string;
}

export async function GET() {
  try {
    // Query pre-aggregated gold KPIs table
    const query = `
      SELECT
        unique_artists AS artists,
        songs_streamed AS songs,
        total_time AS total_hours
      FROM analytics.gold_spotify_kpis
      LIMIT 1
    `;

    const result = await queryClickHouseOne<SummaryStat>(query);

    return NextResponse.json({
      stats: [
        { label: 'Artists', value: result?.artists || '0' },
        { label: 'Songs', value: result?.songs || '0' },
      ],
      totalHours: result?.total_hours || '0 hrs',
    });
  } catch (error) {
    console.error('Error fetching Spotify summary:', error);
    return NextResponse.json(
      { error: 'Failed to fetch summary' },
      { status: 500 }
    );
  }
}
