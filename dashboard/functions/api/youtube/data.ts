/**
 * YouTube Data API Route (Cloudflare Workers Function)
 *
 * Note: Google Takeout YouTube history doesn't include channel names/IDs
 * (grouped by video instead) or actual watch duration (count as proxy).
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
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

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const [kpisResult, topChannels, categoryBreakdown, dailyWatchTimeBreakdown, recentVideos, hourlyActivity] =
        await Promise.all([
          queryClickHouse<YouTubeKPIsWithWatchTime>(env, `SELECT * FROM gold.gold_youtube_kpis_with_watch_time_dashboard LIMIT 1`),
          queryClickHouse<TopChannel>(env, `SELECT * FROM gold.gold_youtube_top_channels_dashboard ORDER BY total_watch_time_seconds DESC LIMIT 10`),
          queryClickHouse<CategoryBreakdown>(env, `SELECT * FROM gold.gold_youtube_category_breakdown_dashboard`),
          queryClickHouse<DailyWatchTimeBreakdown>(env, `SELECT * FROM gold.gold_youtube_daily_watch_time_breakdown_dashboard ORDER BY date ASC`),
          queryClickHouse<RecentVideo>(env, `SELECT * FROM gold.gold_youtube_recent_videos_dashboard LIMIT 10`),
          queryClickHouse<HourlyActivity>(env, `SELECT * FROM gold.gold_youtube_hourly_activity_dashboard`),
        ]);

      const kpis = kpisResult[0] || null;

      return {
        kpis: {
          videosWatched: kpis?.videos_watched?.toLocaleString() || '0',
          totalSearches: kpis?.total_searches?.toLocaleString() || '0',
          totalAdsWatched: kpis?.total_ads_watched?.toLocaleString() || '0',
          adsPercentage: kpis?.ads_percentage?.toFixed(1) || '0',
          totalWatchTime: kpis?.total_watch_time_seconds
            ? `${Math.round(kpis.total_watch_time_seconds / 3600)}h`
            : '0h',
          totalChannels: kpis?.unique_channels?.toLocaleString() || '0',
          avgWatchTimePerDay: Math.round(kpis?.avg_activities_per_day || 0),
          enrichmentPercentage: kpis?.enrichment_percentage?.toFixed(1) || '0',
          firstActivityDate: kpis?.first_activity_date || '',
          lastActivityDate: kpis?.last_activity_date || '',
        },
        topChannels: topChannels.map(c => ({
          channelId: c.channel_id,
          channelTitle: c.channel_title.length > 50 ? c.channel_title.substring(0, 50) + '...' : c.channel_title,
          watchCount: Number(c.watch_count) || 0,
          totalWatchTime: c.total_watch_time_formatted,
          watchTimeHours: Math.round((Number(c.total_watch_time_seconds) || 0) / 3600 * 10) / 10,
          category: c.primary_category,
          uniqueVideos: Number(c.unique_videos_watched) || 0,
        })),
        categoryBreakdown: categoryBreakdown.map(cat => ({
          name: cat.category_name,
          watchCount: Number(cat.watch_count) || 0,
          watchTime: cat.total_watch_time_formatted,
          watchPercentage: Number(cat.watch_percentage) || 0,
          timePercentage: Number(cat.time_percentage) || 0,
          uniqueChannels: Number(cat.unique_channels) || 0,
        })),
        dailyWatchTimeBreakdown: dailyWatchTimeBreakdown.map(d => ({
          date: d.date,
          watchedHours: Number(d.watched_hours) || 0,
          searchesHours: Number(d.searches_hours) || 0,
          visitsHours: Number(d.visits_hours) || 0,
          adsHours: Number(d.ads_hours) || 0,
          otherHours: Number(d.other_hours) || 0,
          totalHours: Number(d.total_hours) || 0,
          watchedCount: Number(d.watched_count) || 0,
          searchesCount: Number(d.searches_count) || 0,
          visitsCount: Number(d.visits_count) || 0,
          adsCount: Number(d.ads_count) || 0,
          dayName: d.day_name,
          isWeekend: d.is_weekend === 1,
        })),
        recentVideos: recentVideos.map(v => ({
          title: v.title.length > 80 ? v.title.substring(0, 80) + '...' : v.title,
          time: v.time,
          relativeTime: v.relative_time,
          timeOfDay: v.time_of_day,
          isFromAds: v.is_from_ads === 1,
        })),
        hourlyActivity: hourlyActivity.map(h => ({
          hour: h.hour,
          activities: Number(h.activities) || 0,
        })),
      };
    },
    'youtube/data',
    request,
    {
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
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);
  return Response.json(body, { headers });
}
