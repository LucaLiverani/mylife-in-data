/**
 * YouTube Data API Route (Cloudflare Workers Function)
 * Queries ClickHouse gold tables for dashboard data
 *
 * Note: Google Takeout YouTube history doesn't include:
 * - Channel names/IDs (grouped by video instead)
 * - Actual watch duration (using video count as proxy)
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';

interface YouTubeKPIs {
  total_videos: number;
  avg_daily: string;
}

interface TopVideo {
  rank: number;
  title: string;
  video_id: string;
  watch_count: number;
  frequency_category: string;
}

interface ActivityType {
  name: string;
  value: number;
  activity_count: number;
}

interface DailyWatch {
  date: string;
  videos_watched: number;
}

interface RecentVideo {
  title: string;
  time: string;
  relative_time: string;
  time_of_day: string;
  is_from_ads: number;
}

interface HourlyActivity {
  hour: string;
  activities: number;
}

/**
 * GET /api/youtube/data
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query gold tables created by dbt
    // These are pre-aggregated and optimized for dashboard queries

    const kpisQuery = `
      SELECT *
      FROM gold.gold_youtube_kpis_dashboard
      LIMIT 1
    `;

    const topVideosQuery = `
      SELECT *
      FROM gold.gold_youtube_top_videos_dashboard
      LIMIT 10
    `;

    const activityTypesQuery = `
      SELECT *
      FROM gold.gold_youtube_activity_types_dashboard
    `;

    const dailyWatchQuery = `
      SELECT *
      FROM gold.gold_youtube_daily_watch_time_dashboard
      ORDER BY date ASC
    `;

    const recentVideosQuery = `
      SELECT *
      FROM gold.gold_youtube_recent_videos_dashboard
      LIMIT 10
    `;

    const hourlyActivityQuery = `
      SELECT *
      FROM gold.gold_youtube_hourly_activity_dashboard
    `;

    // Execute all queries in parallel
    const [kpisResult, topVideos, activityTypes, dailyWatch, recentVideos, hourlyActivity] = await Promise.all([
      queryClickHouse<YouTubeKPIs>(env, kpisQuery),
      queryClickHouse<TopVideo>(env, topVideosQuery),
      queryClickHouse<ActivityType>(env, activityTypesQuery),
      queryClickHouse<DailyWatch>(env, dailyWatchQuery),
      queryClickHouse<RecentVideo>(env, recentVideosQuery),
      queryClickHouse<HourlyActivity>(env, hourlyActivityQuery),
    ]);

    const kpis = kpisResult[0] || null;

    // Format response
    const response = {
      kpis: {
        totalVideos: kpis?.total_videos?.toLocaleString() || '0',
        avgDaily: kpis?.avg_daily || '0 videos',
      },
      topVideos: topVideos.map(video => ({
        rank: video.rank,
        title: video.title.length > 60 ? video.title.substring(0, 60) + '...' : video.title,
        videoId: video.video_id,
        watchCount: Number(video.watch_count) || 0,
        category: video.frequency_category,
      })),
      activityTypes: activityTypes.map(type => ({
        name: type.name,
        value: Number(type.value) || 0,
        count: Number(type.activity_count) || 0,
      })),
      dailyWatch: {
        dates: dailyWatch.map(d => d.date),
        values: dailyWatch.map(d => Number(d.videos_watched) || 0),
      },
      recentVideos: recentVideos.map(video => ({
        title: video.title.length > 80 ? video.title.substring(0, 80) + '...' : video.title,
        time: video.time,
        relativeTime: video.relative_time,
        timeOfDay: video.time_of_day,
        isFromAds: video.is_from_ads === 1,
      })),
      hourlyActivity: hourlyActivity.map(h => ({
        hour: h.hour,
        activities: Number(h.activities) || 0,
      })),
    };

    return Response.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (error) {
    console.error('Error fetching YouTube data:', error);

    // Return empty data instead of error to allow page to load
    return Response.json({
      kpis: {
        totalVideos: '0',
        avgDaily: '0 videos',
      },
      topVideos: [],
      activityTypes: [],
      dailyWatch: {
        dates: [],
        values: [],
      },
      recentVideos: [],
      hourlyActivity: [],
    });
  }
}
