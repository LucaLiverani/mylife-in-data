/**
 * POST /api/internal/calendar-webhook
 *
 * Google calls this endpoint on every Calendar `events.watch` notification.
 * Headers:
 *   X-Goog-Channel-Token   — must match env.CALENDAR_WEBHOOK_TOKEN
 *   X-Goog-Channel-ID      — our channel UUID
 *   X-Goog-Resource-ID     — Google's resource ID
 *   X-Goog-Resource-State  — "sync" (handshake), "exists", "not_exists"
 *   X-Goog-Message-Number  — monotonic per channel
 *
 * Returns 200 quickly so Google doesn't retry. The Dagster sync sensor reads
 * `bronze.calendar_sync_notifications` to pick up unprocessed deltas.
 */

import type { Env } from '../../_shared/types';
import { queryClickHouse } from '../../_shared/clickhouse';

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  if (request.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  if (!env.CALENDAR_WEBHOOK_TOKEN) {
    return new Response('CALENDAR_WEBHOOK_TOKEN not configured', { status: 500 });
  }

  const headerToken = request.headers.get('x-goog-channel-token') || '';
  if (headerToken !== env.CALENDAR_WEBHOOK_TOKEN) {
    return new Response('forbidden', { status: 403 });
  }

  const channelId = request.headers.get('x-goog-channel-id') || '';
  const resourceId = request.headers.get('x-goog-resource-id') || '';
  const state = request.headers.get('x-goog-resource-state') || '';
  const messageNumberRaw = request.headers.get('x-goog-message-number') || '0';
  const messageNumber = Number(messageNumberRaw) || 0;

  // The "sync" state is the initial handshake (no actual event change).
  // Acknowledge and skip the insert.
  if (state === 'sync') {
    return new Response('ok (sync)', { status: 200 });
  }

  // Resolve calendar_id from channel_id (auth.calendar_channels). If unknown,
  // we still insert with an empty calendar_id — the Dagster drainer will skip
  // these but they're recorded for audit.
  const esc = (s: string) => s.replace(/'/g, "''");

  // ClickHouse INSERT … VALUES with a sub-select isn't supported directly.
  // Do the join in two steps via the unified queryClickHouse helper.
  const calRows = await queryClickHouse<{ calendar_id: string }>(
    env,
    `SELECT calendar_id FROM auth.calendar_channels FINAL WHERE channel_id='${esc(channelId)}' LIMIT 1`
  );
  const calendarId = calRows[0]?.calendar_id || '';

  const insertSql =
    `INSERT INTO bronze.calendar_sync_notifications ` +
    `(received_at, channel_id, resource_id, calendar_id, message_number) ` +
    `VALUES (now64(), '${esc(channelId)}', '${esc(resourceId)}', '${esc(calendarId)}', ${messageNumber})`;

  try {
    await queryClickHouse(env, insertSql);
  } catch (err) {
    console.error('calendar-webhook insert failed:', err);
    // Still 200 to avoid Google retries piling up — the issue is on our side.
  }

  return new Response('ok', { status: 200 });
}
