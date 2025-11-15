/**
 * Overview Stats API Route
 * Provides aggregated statistics for the dashboard overview
 */

import { NextResponse } from 'next/server';
import { queryClickHouse } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';
export const revalidate = 60;

export async function GET() {
  try {
    // Get summary stats from existing gold tables
    const summaryQuery = `
      SELECT
        total_plays_raw AS songsStreamed,
        '0' AS videosWatched,
        '0' AS searchQueries,
        '0' AS citiesVisited
      FROM analytics_gold.gold_spotify_kpis
      LIMIT 1
    `;

    // Get daily listening data for the chart (last 30 days)
    const dataGenQuery = `
      SELECT
        date,
        play_count AS spotify,
        0 AS youtube,
        0 AS google,
        0 AS maps
      FROM analytics_gold.gold_spotify_daily_listening
      ORDER BY date DESC
      LIMIT 30
    `;

    const [summaryResult, dataGenResult] = await Promise.all([
      queryClickHouse<{ songsStreamed: string; videosWatched: string; searchQueries: string; citiesVisited: string }>(summaryQuery),
      queryClickHouse<{ date: string; spotify: number; youtube: number; google: number; maps: number }>(dataGenQuery),
    ]);

    // Parse songs streamed to remove decimals
    const rawSummary = summaryResult[0] || {
      songsStreamed: '0',
      videosWatched: '0',
      searchQueries: '0',
      citiesVisited: '0',
    };

    const summary = {
      songsStreamed: parseInt(String(rawSummary.songsStreamed), 10).toString(),
      videosWatched: rawSummary.videosWatched,
      searchQueries: rawSummary.searchQueries,
      citiesVisited: rawSummary.citiesVisited,
    };

    // Reverse to show oldest to newest
    const reversedData = dataGenResult.reverse();

    const dates = reversedData.map(r => r.date);
    const spotify = reversedData.map(r => r.spotify);
    const youtube = reversedData.map(r => r.youtube);
    const google = reversedData.map(r => r.google);
    const maps = reversedData.map(r => r.maps);

    const totalEvents = spotify.reduce((a, b) => a + b, 0) +
                        youtube.reduce((a, b) => a + b, 0) +
                        google.reduce((a, b) => a + b, 0) +
                        maps.reduce((a, b) => a + b, 0);

    const avgPerDay = dates.length > 0 ? Math.round(totalEvents / dates.length) : 0;

    return NextResponse.json({
      summary,
      dataGeneration: {
        dates,
        spotify,
        youtube,
        google,
        maps,
        totalEvents: totalEvents.toString(),
        avgPerDay: avgPerDay.toString(),
      },
    });
  } catch (error) {
    console.error('Error fetching overview stats:', error);

    // Return mock data as fallback
    return NextResponse.json({
      summary: {
        songsStreamed: '0',
        videosWatched: '0',
        searchQueries: '0',
        citiesVisited: '0',
      },
      dataGeneration: {
        dates: [],
        spotify: [],
        youtube: [],
        google: [],
        maps: [],
        totalEvents: '0',
        avgPerDay: '0',
      },
    });
  }
}
