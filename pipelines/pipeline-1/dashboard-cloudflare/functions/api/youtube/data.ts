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

interface YouTubeKPIsWithWatchTime {
  videos_watched: number;
  total_searches: number;
  total_ads_watched: number;
  ads_percentage: number;
  total_watch_time_seconds: number;
  total_watch_time_formatted: string;
  avg_watch_time_seconds: number;
  avg_watch_time_formatted: string;
  unique_channels: number;
  unique_videos: number;
  unique_categories: number;
  avg_activities_per_day: number;
  avg_watched_per_day: number;
  enrichment_percentage: number;
  first_activity_date: string;
  last_activity_date: string;
}

interface TopChannel {
  channel_id: string;
  channel_title: string;
  watch_count: number;
  total_watch_time_seconds: number;
  total_watch_time_formatted: string;
  primary_category: string;
  unique_videos_watched: number;
}

interface CategoryBreakdown {
  category_name: string;
  watch_count: number;
  total_watch_time_seconds: number;
  total_watch_time_formatted: string;
  watch_percentage: number;
  time_percentage: number;
  unique_channels: number;
}

interface ActivityType {
  name: string;
  value: number;
  activity_count: number;
}

interface DailyWatchTimeBreakdown {
  date: string;
  watched_hours: number;
  searches_hours: number;
  visits_hours: number;
  ads_hours: number;
  other_hours: number;
  total_hours: number;
  watched_count: number;
  searches_count: number;
  visits_count: number;
  ads_count: number;
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
      FROM gold.gold_youtube_kpis_with_watch_time_dashboard
      LIMIT 1
    `;

    const topChannelsQuery = `
      SELECT *
      FROM gold.gold_youtube_top_channels_dashboard
      ORDER BY total_watch_time_seconds DESC
      LIMIT 10
    `;

    const categoryBreakdownQuery = `
      SELECT *
      FROM gold.gold_youtube_category_breakdown_dashboard
    `;

    const dailyWatchTimeBreakdownQuery = `
      SELECT *
      FROM gold.gold_youtube_daily_watch_time_breakdown_dashboard
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
    const [kpisResult, topChannels, categoryBreakdown, dailyWatchTimeBreakdown, recentVideos, hourlyActivity] = await Promise.all([
      queryClickHouse<YouTubeKPIsWithWatchTime>(env, kpisQuery),
      queryClickHouse<TopChannel>(env, topChannelsQuery),
      queryClickHouse<CategoryBreakdown>(env, categoryBreakdownQuery),
      queryClickHouse<DailyWatchTimeBreakdown>(env, dailyWatchTimeBreakdownQuery),
      queryClickHouse<RecentVideo>(env, recentVideosQuery),
      queryClickHouse<HourlyActivity>(env, hourlyActivityQuery),
    ]);

    const kpis = kpisResult[0] || null;

    // Format response
    const response = {
      kpis: {
        videosWatched: kpis?.videos_watched?.toLocaleString() || '0',
        totalSearches: kpis?.total_searches?.toLocaleString() || '0',
        totalAdsWatched: kpis?.total_ads_watched?.toLocaleString() || '0',
        adsPercentage: kpis?.ads_percentage?.toFixed(1) || '0',
        // Format watch time as hours only for fixed size display
        totalWatchTime: kpis?.total_watch_time_seconds
          ? `${Math.round(kpis.total_watch_time_seconds / 3600)}h`
          : '0h',
        totalChannels: kpis?.unique_channels?.toLocaleString() || '0',
        avgWatchTimePerDay: Math.round(kpis?.avg_activities_per_day || 0),
        enrichmentPercentage: kpis?.enrichment_percentage?.toFixed(1) || '0',
        firstActivityDate: kpis?.first_activity_date || '',
        lastActivityDate: kpis?.last_activity_date || '',
      },
      topChannels: topChannels.map(channel => ({
        channelId: channel.channel_id,
        channelTitle: channel.channel_title.length > 50 ? channel.channel_title.substring(0, 50) + '...' : channel.channel_title,
        watchCount: Number(channel.watch_count) || 0,
        totalWatchTime: channel.total_watch_time_formatted,
        watchTimeHours: Math.round((Number(channel.total_watch_time_seconds) || 0) / 3600 * 10) / 10, // Round to 1 decimal
        category: channel.primary_category,
        uniqueVideos: Number(channel.unique_videos_watched) || 0,
      })),
      categoryBreakdown: categoryBreakdown.map(cat => ({
        name: cat.category_name,
        watchCount: Number(cat.watch_count) || 0,
        watchTime: cat.total_watch_time_formatted,
        watchPercentage: Number(cat.watch_percentage) || 0,
        timePercentage: Number(cat.time_percentage) || 0,
        uniqueChannels: Number(cat.unique_channels) || 0,
      })),
      dailyWatchTimeBreakdown: dailyWatchTimeBreakdown.map(day => ({
        date: day.date,
        watchedHours: Number(day.watched_hours) || 0,
        searchesHours: Number(day.searches_hours) || 0,
        visitsHours: Number(day.visits_hours) || 0,
        adsHours: Number(day.ads_hours) || 0,
        otherHours: Number(day.other_hours) || 0,
        totalHours: Number(day.total_hours) || 0,
        watchedCount: Number(day.watched_count) || 0,
        searchesCount: Number(day.searches_count) || 0,
        visitsCount: Number(day.visits_count) || 0,
        adsCount: Number(day.ads_count) || 0,
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
        videosWatched: '0',
        totalSearches: '0',
        totalAdsWatched: '0',
        adsPercentage: '0',
        totalWatchTime: '0h',
        totalChannels: '0',
        avgWatchTimePerDay: 0,
        enrichmentPercentage: '0',
        firstActivityDate: '',
        lastActivityDate: '',
      },
      topChannels: [],
      categoryBreakdown: [],
      dailyWatchTimeBreakdown: [],
      recentVideos: [],
      hourlyActivity: [],
    });
  }
}
