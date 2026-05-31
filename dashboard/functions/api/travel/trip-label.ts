/**
 * POST /api/travel/trip-label  — owner-only trip confirm / reject / edit.
 *
 * Writes one row to silver.maps_trip_labels (ReplacingMergeTree, latest per
 * trip_key wins); gold_maps_trips reads it live, so the next /api/travel/data
 * fetch reflects the override (a 'reject' drops the trip from the public list).
 *
 * Auth: the request must carry the shared owner token in `x-trip-label-token`,
 * matched against env.TRIP_LABEL_TOKEN. Without it the endpoint is inert, so
 * the public dashboard can read trips but never mutate them.
 */

import type { Env } from '../../_shared/types';
import { queryClickHouse } from '../../_shared/clickhouse';

const LABELS = new Set(['confirm', 'reject', 'edit']);
const TRIP_KEY_RE = /^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}$/;

interface LabelBody {
  trip_key?: string;
  label?: string;
  edited_title?: string;
  edited_destination?: string;
  edited_trip_type?: string;
  note?: string;
}

const esc = (s: string) => s.replace(/'/g, "''");
const clip = (s: unknown, n: number) => String(s ?? '').slice(0, n);

export async function onRequest(context: { env: Env; request: Request }): Promise<Response> {
  const { env, request } = context;

  if (request.method !== 'POST') {
    return Response.json({ ok: false, error: 'method not allowed' }, { status: 405 });
  }
  if (!env.TRIP_LABEL_TOKEN) {
    return Response.json({ ok: false, error: 'labeling not configured' }, { status: 503 });
  }
  if ((request.headers.get('x-trip-label-token') || '') !== env.TRIP_LABEL_TOKEN) {
    return Response.json({ ok: false, error: 'forbidden' }, { status: 403 });
  }

  let body: LabelBody;
  try {
    body = (await request.json()) as LabelBody;
  } catch {
    return Response.json({ ok: false, error: 'invalid JSON' }, { status: 400 });
  }

  const tripKey = String(body.trip_key || '');
  const label = String(body.label || '');
  if (!TRIP_KEY_RE.test(tripKey)) {
    return Response.json({ ok: false, error: 'invalid trip_key' }, { status: 400 });
  }
  if (!LABELS.has(label)) {
    return Response.json({ ok: false, error: 'invalid label' }, { status: 400 });
  }

  // Edited fields only matter for 'edit'; ignore them otherwise so a stray
  // confirm/reject can't smuggle overrides in.
  const editedTitle = label === 'edit' ? clip(body.edited_title, 200) : '';
  const editedDest = label === 'edit' ? clip(body.edited_destination, 200) : '';
  const editedType = label === 'edit' ? clip(body.edited_trip_type, 32) : '';
  const note = clip(body.note, 500);

  const sql =
    `INSERT INTO silver.maps_trip_labels ` +
    `(trip_key, label, edited_title, edited_destination, edited_trip_type, note) VALUES (` +
    `'${esc(tripKey)}', '${esc(label)}', '${esc(editedTitle)}', ` +
    `'${esc(editedDest)}', '${esc(editedType)}', '${esc(note)}')`;

  try {
    await queryClickHouse(env, sql);
  } catch (err) {
    console.error('trip-label insert failed:', err);
    return Response.json({ ok: false, error: 'write failed' }, { status: 500 });
  }

  return Response.json({ ok: true, trip_key: tripKey, label });
}
