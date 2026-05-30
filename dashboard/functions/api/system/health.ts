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

      // Freshness threshold (seconds) before a channel is "stale".
      const FRESH_LIMIT_S: Record<string, number> = {
        spotify: 86400,        // recently-played history
        youtube: 86400 * 2,
        maps: 86400 * 3,       // daily DP, allow slack
        calendar: 86400 * 2,
      };

      const bySource: Record<string, SourceFreshness> = {};
      for (const s of sources) bySource[s.source] = s;

      const humanizeAgo = (sec: number | null): string => {
        if (sec === null || !Number.isFinite(sec) || sec < 0) return '—';
        if (sec < 90) return `${Math.round(sec)}s ago`;
        if (sec < 5400) return `${Math.round(sec / 60)}m ago`;
        if (sec < 172800) return `${Math.round(sec / 3600)}h ago`;
        return `${Math.round(sec / 86400)}d ago`;
      };

      const mkChannel = (channel: string, s: SourceFreshness | undefined, limit: number) => {
        const sec = s ? Number(s.seconds_since) : null;
        const has = s != null && s.last_event_at != null && s.last_event_at !== '';
        return {
          channel,
          status: !has ? 'down' : (sec !== null && sec <= limit ? 'healthy' : 'stale'),
          lastBatchAgo: has ? humanizeAgo(sec) : 'never',
          eventsPerHour: s ? Math.round((Number(s.rows_24h) || 0) / 24) : 0,
          errors24h: 0,
        };
      };

      // Collapse spotify + spotify_history into the single "spotify" channel
      // (the player-current table is empty between plays; history is the signal).
      const channels = [
        mkChannel('spotify', bySource['spotify_history'] ?? bySource['spotify'], FRESH_LIMIT_S.spotify),
        mkChannel('youtube', bySource['youtube'], FRESH_LIMIT_S.youtube),
        mkChannel('maps', bySource['maps'], FRESH_LIMIT_S.maps),
        mkChannel('calendar', bySource['calendar'], FRESH_LIMIT_S.calendar),
      ];

      const rank: Record<string, number> = { healthy: 0, degraded: 1, stale: 2, down: 3 };
      const worst = channels.reduce((acc, c) => (rank[c.status] > rank[acc] ? c.status : acc), 'healthy');
      const staleN = channels.filter(c => c.status !== 'healthy').length;

      const totalRows = storage.reduce((a, s) => a + (Number(s.rows) || 0), 0);
      const totalDiskMb = Math.round(storage.reduce((a, s) => a + (Number(s.bytes_on_disk) || 0), 0) / (1024 * 1024));

      return {
        generatedAt: new Date().toISOString(),
        overall: {
          status: worst,
          summary: staleN === 0 ? 'All channels healthy' : `${staleN} channel${staleN > 1 ? 's' : ''} need attention`,
        },
        channels,
        storage: {
          name: 'ClickHouse',
          status: 'healthy',
          rowCount: totalRows,
          diskUsedMb: totalDiskMb,
          byDatabase: storage.map(s => ({
            database: s.database,
            rows: Number(s.rows) || 0,
            diskUsedMb: Math.round((Number(s.bytes_on_disk) || 0) / (1024 * 1024)),
          })),
        },
        errors24h: alerts.map(a => ({
          time: a.raised_at,
          channel: 'platform',
          severity: 'warn',
          message: a.message || a.kind,
        })),
      };
    },
    'system/health',
    request,
    {
      generatedAt: new Date().toISOString(),
      overall: { status: 'stale', summary: 'Health data unavailable' },
      channels: [],
      storage: { name: 'ClickHouse', status: 'stale', rowCount: 0, diskUsedMb: 0, byDatabase: [] },
      errors24h: [],
    }
  );

  const { body, headers } = addCacheHeaders(data, isFromCache, error, 'public, max-age=30');
  return Response.json(body, { headers });
}
