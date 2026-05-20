/**
 * Home Recent Events API Route (Cloudflare Workers Function)
 * Aggregates recent events from all sources using gold model
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import type { Env } from '../../_shared/types';

interface RecentEvent {
  source: string;
  recency_rank: number;
  title: string;
  subtitle: string;
  time: string;
  image_url: string;
  activity_type: string;
  metadata: string;
  is_from_ads: number;
}

/**
 * GET /api/home/recent-events
 */
export async function onRequest(context: { env: Env }): Promise<Response> {
  const { env } = context;

  try {
    // Query unified recent events from gold model
    const query = `
      SELECT *
      FROM gold.gold_home_recent_events
      ORDER BY source, recency_rank
    `;

    const events = await queryClickHouse<RecentEvent>(env, query);

    // Group events by source
    const spotify = events
      .filter(e => e.source === 'spotify')
      .map(e => ({
        track: e.title,
        artist: e.subtitle,
        time: e.time,
        relativeTime: e.metadata,
        albumArt: e.image_url || `https://picsum.photos/seed/${e.subtitle}/100`,
      }));

    const youtube = events
      .filter(e => e.source === 'youtube')
      .map(e => ({
        title: e.title.length > 80 ? e.title.substring(0, 80) + '...' : e.title,
        activityType: e.activity_type,
        time: e.time,
        isFromAds: e.is_from_ads === 1,
        relativeTime: e.subtitle,
      }));

    const maps = events
      .filter(e => e.source === 'maps')
      .map(e => ({
        location: e.title,
        type: e.subtitle,
        time: e.time,
        timeOfDay: e.metadata,
      }));

    const response = { spotify, youtube, maps };

    return Response.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (error) {
    console.error('Error fetching recent events:', error);

    // Return empty data instead of error to allow page to load
    return Response.json({
      spotify: [],
      youtube: [],
      maps: [],
    });
  }
}
