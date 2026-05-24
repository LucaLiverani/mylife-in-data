/**
 * GET /api/system/health
 *
 * Per-source freshness, last-batch latency, storage stats, and any open
 * alerts from `auth.alerts`. Queried directly at request time — no gold
 * table because the value is "live status", not aggregated history.
 */

import { queryClickHouse } from '../../_shared/clickhouse';
import { queryWithFallback, addCacheHeaders } from '../../_shared/fallback';
import type { Env } from '../../_shared/types';


interface SourceFreshness {
  source: string;
  last_event_at: string | null;
  seconds_since: number;
  rows_24h: number;
}

interface AlertRow {
  raised_at: string;
  kind: string;
  account_email: string;
  message: string;
}

interface StorageRow {
  database: string;
  rows: number;
  bytes_on_disk: number;
}

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  const { data, isFromCache, error } = await queryWithFallback<any>(
    async () => {
      const freshnessSql = `
        WITH sources AS (
          SELECT 'spotify'  AS source, max(captured_at)::String AS last_event_at,
                 dateDiff('second', max(captured_at), now()) AS seconds_since,
                 countIf(captured_at >= now() - INTERVAL 24 HOUR) AS rows_24h
          FROM bronze.spotify_player_current
          UNION ALL
          SELECT 'spotify_history', max(played_at)::String, dateDiff('second', max(played_at), now()),
                 countIf(played_at >= now() - INTERVAL 24 HOUR)
          FROM bronze.spotify_plays_raw
          UNION ALL
          SELECT 'youtube',  max(watched_at)::String, dateDiff('second', max(watched_at), now()),
                 countIf(watched_at >= now() - INTERVAL 24 HOUR)
          FROM bronze.youtube_watch_history
          UNION ALL
          SELECT 'maps',     max(started_at)::String, dateDiff('second', max(started_at), now()),
                 countIf(started_at >= now() - INTERVAL 24 HOUR)
          FROM bronze.maps_visits
          UNION ALL
          SELECT 'calendar', max(started_at)::String, dateDiff('second', max(started_at), now()),
                 countIf(_ingested_at >= now() - INTERVAL 24 HOUR)
          FROM bronze.calendar_events
        )
        SELECT * FROM sources ORDER BY source
      `;

      const alertsSql =
        `SELECT raised_at::String AS raised_at, kind, account_email, message ` +
        `FROM auth.alerts ` +
        `WHERE raised_at >= now() - INTERVAL 7 DAY ` +
        `ORDER BY raised_at DESC LIMIT 50`;

      const storageSql = `
        SELECT
          database,
          sum(rows)          AS rows,
          sum(bytes_on_disk) AS bytes_on_disk
        FROM system.parts
        WHERE database IN ('bronze','silver','gold','auth') AND active
        GROUP BY database
        ORDER BY database
      `;

      const [sources, alerts, storage] = await Promise.all([
        queryClickHouse<SourceFreshness>(env, freshnessSql),
        queryClickHouse<AlertRow>(env, alertsSql),
        queryClickHouse<StorageRow>(env, storageSql),
      ]);

      const FRESH_LIMIT_S: Record<string, number> = {
        spotify: 300,
        spotify_history: 86400,
        youtube: 86400 * 2,
        maps: 86400 * 2,
        calendar: 86400 * 2,
      };

      const perSource = sources.map(s => ({
        source: s.source,
        lastEventAt: s.last_event_at,
        secondsSinceLastEvent: Number(s.seconds_since) || 0,
        rows24h: Number(s.rows_24h) || 0,
        status:
          Number(s.seconds_since) <= (FRESH_LIMIT_S[s.source] ?? 86400)
            ? 'ok'
            : 'stale',
      }));

      return {
        timestamp: new Date().toISOString(),
        perSource,
        alerts: alerts.map(a => ({
          raisedAt: a.raised_at,
          kind: a.kind,
          accountEmail: a.account_email,
          message: a.message,
        })),
        storage: storage.map(s => ({
          database: s.database,
          rows: Number(s.rows) || 0,
          diskUsedMb: Math.round((Number(s.bytes_on_disk) || 0) / (1024 * 1024)),
        })),
      };
    },
    'system/health',
    request,
    { timestamp: new Date().toISOString(), perSource: [], alerts: [], storage: [] }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error, 'public, max-age=30');
  return Response.json(body, { headers });
}
