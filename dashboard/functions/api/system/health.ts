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
      // Every timestamp expression is wrapped in toDateTime64(col, 3)/toString()
      // so the query is robust to a column being stored as String on one
      // environment and DateTime on another (schema drift). The bare comparison
      // `col >= now() - INTERVAL 24 HOUR` threw NO_COMMON_TYPE on prod (a String
      // column vs DateTime literal); toDateTime64(col, 3) normalises it AND
      // parses millisecond-precision strings that plain toDateTime() rejects.
      // maps reads the activity table (Timeline-era maps_visits is empty);
      // calendar uses _ingested_at so future-dated events don't skew freshness.
      const freshnessSql = `
        WITH sources AS (
          SELECT 'spotify'  AS source, toString(max(captured_at)) AS last_event_at,
                 dateDiff('second', toDateTime64(max(captured_at), 3), now()) AS seconds_since,
                 countIf(toDateTime64(captured_at, 3) >= now() - INTERVAL 24 HOUR) AS rows_24h
          FROM bronze.spotify_player_current
          UNION ALL
          SELECT 'spotify_history', toString(max(played_at)), dateDiff('second', toDateTime64(max(played_at), 3), now()),
                 countIf(toDateTime64(played_at, 3) >= now() - INTERVAL 24 HOUR)
          FROM bronze.spotify_plays_raw
          UNION ALL
          SELECT 'youtube',  toString(max(watched_at)), dateDiff('second', toDateTime64(max(watched_at), 3), now()),
                 countIf(toDateTime64(watched_at, 3) >= now() - INTERVAL 24 HOUR)
          FROM bronze.youtube_watch_history
          UNION ALL
          SELECT 'maps',     toString(max(event_ts)), dateDiff('second', toDateTime64(max(event_ts), 3), now()),
                 countIf(toDateTime64(event_ts, 3) >= now() - INTERVAL 24 HOUR)
          FROM bronze.maps_activity
          UNION ALL
          SELECT 'calendar', toString(max(_ingested_at)), dateDiff('second', toDateTime64(max(_ingested_at), 3), now()),
                 countIf(toDateTime64(_ingested_at, 3) >= now() - INTERVAL 24 HOUR)
          FROM bronze.calendar_events
        )
        SELECT * FROM sources ORDER BY source
      `;

      // toDateTime64(raised_at, 3) in the WHERE: same String-vs-DateTime
      // robustness as the freshness query (auth.alerts.raised_at may be String).
      const alertsSql =
        `SELECT toString(raised_at) AS raised_at, kind, account_email, message ` +
        `FROM auth.alerts ` +
        `WHERE toDateTime64(raised_at, 3) >= now() - INTERVAL 7 DAY ` +
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
