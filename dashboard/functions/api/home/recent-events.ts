/**
 * Home Recent Events API Route (Cloudflare Workers Function)
 * Aggregates recent events from all sources using gold model.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface RecentEvent {
  source: string;
  recency_rank: number;
  title: string;
  subtitle: string;
  time: string;
  image_url: string;
  activity_type: string;
  is_from_ads: number;
}

interface RecentEventsResponse {
  spotify: any[];
  youtube: any[];
  maps: any[];
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<RecentEventsResponse>(
    async () => {
      const query = `
        SELECT *
        FROM gold.gold_home_recent_events
        ORDER BY source, recency_rank
      `;
      const events = await queryClickHouse<RecentEvent>(env, query);

      const spotify = events
        .filter(e => e.source === 'spotify')
        .map(e => ({
          track: e.title,
          artist: e.subtitle,
          time: e.time,
          albumArt: e.image_url || `https://picsum.photos/seed/${e.subtitle}/100`,
        }));

      const youtube = events
        .filter(e => e.source === 'youtube')
        .map(e => ({
          title: e.title.length > 80 ? e.title.substring(0, 80) + '...' : e.title,
          activityType: e.activity_type,
          time: e.time,
          isFromAds: e.is_from_ads === 1,
        }));

      const maps = events
        .filter(e => e.source === 'maps')
        .map(e => ({
          location: e.title,
          type: e.subtitle,
          time: e.time,
        }));

      return { spotify, youtube, maps };
    },
    'home/recent-events',
    request,
    { spotify: [], youtube: [], maps: [] }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error);
  return Response.json(body, { headers });
}
