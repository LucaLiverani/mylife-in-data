/**
 * Overview Stats API Route (Cloudflare Workers Function)
 * Provides aggregated statistics for the dashboard overview
 *
 * This is a direct port from the Next.js API route at:
 * dashboard-nextjs/app/api/overview/stats/route.ts
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface OverviewStats {
  summary: {
    songsStreamed: string;
    artistsListened: string;
    videosWatched: string;
    youtubeChannels: string;
    searchQueries: string;
    citiesVisited: string;
    spotifyHours: number | string;
    youtubeHours: number | string;
  };
  dataGeneration: {
    dates: string[];
    spotify: number[];
    youtube: number[];
    calendar: number[];
    maps: number[];
    totalEvents: string;
    avgPerDay: string;
  };
}

/**
 * Cloudflare Pages Function handler
 * GET /api/overview/stats
 */
export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback(
    async () => {
    // Get summary stats from dashboard view
    const summaryQuery = `
      SELECT *
      FROM gold.gold_home_overview_stats
      LIMIT 1
    `;

    // Get daily listening data for the chart (last 30 days)
    const dataGenQuery = `
      SELECT *
      FROM gold.gold_home_daily_data_generation
      ORDER BY date DESC
      LIMIT 30
    `;

    // Execute queries in parallel
    const [summaryResult, dataGenResult] = await Promise.all([
      queryClickHouse<{ songsStreamed: string; artistsListened: string; videosWatched: string; youtubeChannels: string; searchQueries: string; citiesVisited: string; spotifyHours: number; youtubeHours: number }>(
        env,
        summaryQuery
      ),
      queryClickHouse<{ date: string; spotify: number; youtube: number; google: number; maps: number }>(
        env,
        dataGenQuery
      ),
    ]);

    // Parse songs streamed to remove decimals
    const rawSummary = summaryResult[0] || {
      songsStreamed: '0',
      artistsListened: '0',
      videosWatched: '0',
      youtubeChannels: '0',
      searchQueries: '0',
      citiesVisited: '0',
      spotifyHours: 0,
      youtubeHours: 0,
    };

    const summary = {
      songsStreamed: parseInt(String(rawSummary.songsStreamed), 10).toString(),
      artistsListened: parseInt(String(rawSummary.artistsListened), 10).toString(),
      videosWatched: rawSummary.videosWatched,
      youtubeChannels: rawSummary.youtubeChannels,
      searchQueries: rawSummary.searchQueries,
      citiesVisited: parseInt(String(rawSummary.citiesVisited), 10).toString(),
      spotifyHours: Number(rawSummary.spotifyHours) || 0,
      youtubeHours: Number(rawSummary.youtubeHours) || 0,
    };

    // Reverse to show oldest to newest
    const reversedData = dataGenResult.reverse();

    const dates = reversedData.map(r => r.date);
    // Explicitly convert to numbers to avoid string concatenation issues
    const spotify = reversedData.map(r => Number(r.spotify) || 0);
    const youtube = reversedData.map(r => Number(r.youtube) || 0);
    // Gold exposes the calendar series under the legacy column name `google`;
    // surface it as `calendar` to match the mock/chart/Home contract.
    const calendar = reversedData.map(r => Number(r.google) || 0);
    const maps = reversedData.map(r => Number(r.maps) || 0);

    const totalEvents = spotify.reduce((a, b) => a + b, 0) +
                        youtube.reduce((a, b) => a + b, 0) +
                        calendar.reduce((a, b) => a + b, 0) +
                        maps.reduce((a, b) => a + b, 0);

    const avgPerDay = dates.length > 0 ? Math.round(totalEvents / dates.length) : 0;

      return {
        summary,
        dataGeneration: {
          dates,
          spotify,
          youtube,
          calendar,
          maps,
          totalEvents: totalEvents.toString(),
          avgPerDay: avgPerDay.toString(),
        },
      };
    },
    'overview/stats',
    request,
    {
      summary: {
        songsStreamed: '0',
        artistsListened: '0',
        videosWatched: '0',
        youtubeChannels: '0',
        searchQueries: '0',
        citiesVisited: '0',
        spotifyHours: 0,
        youtubeHours: 0,
      },
      dataGeneration: {
        dates: [],
        spotify: [],
        youtube: [],
        calendar: [],
        maps: [],
        totalEvents: '0',
        avgPerDay: '0',
      },
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);

  return Response.json(body, { headers });
}
