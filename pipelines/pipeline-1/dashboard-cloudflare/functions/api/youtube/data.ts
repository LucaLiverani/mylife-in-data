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

interface YouTubeKPIsEnhanced {
  total_videos: number;
  total_watched: number;
  total_searches: number;
  total_visits: number;
  total_subscriptions: number;
  total_likes: number;
  total_comments: number;
  total_shares: number;
  total_ads_watched: number;
  total_activities: number;
  avg_activities_per_day: number;
  avg_videos_per_day: number;
  ads_percentage: number;
  total_videos_formatted: string;
  total_watched_formatted: string;
  total_searches_formatted: string;
  total_ads_watched_formatted: string;
  first_activity_date: string;
  last_activity_date: string;
  days_span: number;
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

interface DailyActivityBreakdown {
  date: string;
  watched: number;
  searches: number;
  visits: number;
  subscriptions: number;
  likes: number;
  comments: number;
  shares: number;
  ads: number;
  other: number;
  total_activities: number;
  unique_videos: number;
  day_name: string;
  is_weekend: number;
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
      FROM gold.gold_youtube_kpis_enhanced_dashboard
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

    const dailyActivityBreakdownQuery = `
      SELECT *
      FROM gold.gold_youtube_daily_activity_breakdown_dashboard
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
    const [kpisResult, topVideos, activityTypes, dailyActivityBreakdown, recentVideos, hourlyActivity] = await Promise.all([
      queryClickHouse<YouTubeKPIsEnhanced>(env, kpisQuery),
      queryClickHouse<TopVideo>(env, topVideosQuery),
      queryClickHouse<ActivityType>(env, activityTypesQuery),
      queryClickHouse<DailyActivityBreakdown>(env, dailyActivityBreakdownQuery),
      queryClickHouse<RecentVideo>(env, recentVideosQuery),
      queryClickHouse<HourlyActivity>(env, hourlyActivityQuery),
    ]);

    const kpis = kpisResult[0] || null;

    // Format response
    const response = {
      kpis: {
        totalVideos: kpis?.total_videos_formatted || '0',
        totalWatched: kpis?.total_watched_formatted || '0',
        totalSearches: kpis?.total_searches_formatted || '0',
        totalAdsWatched: kpis?.total_ads_watched_formatted || '0',
        totalActivities: kpis?.total_activities?.toLocaleString() || '0',
        avgVideosPerDay: kpis?.avg_videos_per_day?.toFixed(1) || '0',
        avgActivitiesPerDay: kpis?.avg_activities_per_day?.toFixed(1) || '0',
        adsPercentage: kpis?.ads_percentage?.toFixed(1) || '0',
        // Additional activity counts
        totalVisits: kpis?.total_visits?.toLocaleString() || '0',
        totalSubscriptions: kpis?.total_subscriptions?.toLocaleString() || '0',
        totalLikes: kpis?.total_likes?.toLocaleString() || '0',
        firstActivityDate: kpis?.first_activity_date || '',
        lastActivityDate: kpis?.last_activity_date || '',
        daysSpan: kpis?.days_span || 0,
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
      dailyActivityBreakdown: dailyActivityBreakdown.map(day => ({
        date: day.date,
        watched: Number(day.watched) || 0,
        searches: Number(day.searches) || 0,
        visits: Number(day.visits) || 0,
        subscriptions: Number(day.subscriptions) || 0,
        likes: Number(day.likes) || 0,
        comments: Number(day.comments) || 0,
        shares: Number(day.shares) || 0,
        ads: Number(day.ads) || 0,
        other: Number(day.other) || 0,
        totalActivities: Number(day.total_activities) || 0,
        uniqueVideos: Number(day.unique_videos) || 0,
        dayName: day.day_name,
        isWeekend: day.is_weekend === 1,
      })),
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
        totalWatched: '0',
        totalSearches: '0',
        totalAdsWatched: '0',
        totalActivities: '0',
        avgVideosPerDay: '0',
        avgActivitiesPerDay: '0',
        adsPercentage: '0',
        totalVisits: '0',
        totalSubscriptions: '0',
        totalLikes: '0',
        firstActivityDate: '',
        lastActivityDate: '',
        daysSpan: 0,
      },
      topVideos: [],
      activityTypes: [],
      dailyActivityBreakdown: [],
      recentVideos: [],
      hourlyActivity: [],
    });
  }
}
