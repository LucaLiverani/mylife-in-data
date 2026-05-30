/**
 * GET /api/now/timeline
 *
 * Cross-channel "Live Console" feed — the latest events across Spotify,
 * YouTube, Maps and Calendar, interleaved by time. Backs the Home LiveConsole
 * and the /now page.
 *
 * Pages Functions take precedence over the `_redirects` rewrite that otherwise
 * serves public/mocks/now/timeline.json, so this replaces the mock with real
 * data (and falls back to that same mock if ClickHouse is unreachable).
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';

interface UnifiedRow {
  time: string;       // already ISO-8601 UTC from the query
  channel: string;    // spotify | youtube | maps | calendar
  kind: string;
  title: string;
  subtitle: string;
}

// kind (from silver_events_unified) → human action label
const KIND_LABELS: Record<string, string> = {
  play: 'Played',
  liked: 'Liked',
  watch: 'Watched',
  meeting: 'Event',
  maps_search: 'Searched',
  maps_directions: 'Directions',
  maps_view: 'Viewed',
  maps_other: 'Maps',
};

const INGESTION_CADENCE = {
  spotify: 'real-time stream',
  youtube: 'daily batch (~24h)',
  maps: 'daily batch (~24h)',
  calendar: 'daily batch (~24h)',
};

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const rows = await queryClickHouse<UnifiedRow>(
        env,
        `SELECT
            formatDateTime(event_ts, '%Y-%m-%dT%H:%i:%SZ', 'UTC') AS time,
            source AS channel,
            kind,
            title,
            subtitle
         FROM silver.silver_events_unified
         WHERE event_ts <= now() AND event_ts >= now() - INTERVAL 30 DAY
         ORDER BY event_ts DESC
         LIMIT 60`
      );

      const events = rows
        .map(r => {
          const value = [r.title, r.subtitle].filter(s => s && s.trim() !== '').join(' — ');
          return {
            time: r.time,
            channel: r.channel,
            label: KIND_LABELS[r.kind] ?? r.kind,
            value,
          };
        })
        .filter(e => e.value !== ''); // drop rows with neither title nor subtitle

      const oldestMs = events.length ? new Date(events[events.length - 1].time).getTime() : Date.now();
      const windowMinutes = Math.max(1, Math.round((Date.now() - oldestMs) / 60000));

      return {
        generatedAt: new Date().toISOString(),
        windowMinutes,
        ingestionCadence: INGESTION_CADENCE,
        events,
      };
    },
    'now/timeline',
    request,
    {
      generatedAt: new Date().toISOString(),
      windowMinutes: 0,
      ingestionCadence: INGESTION_CADENCE,
      events: [],
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error, 'public, max-age=15');
  return Response.json(body, { headers });
}
