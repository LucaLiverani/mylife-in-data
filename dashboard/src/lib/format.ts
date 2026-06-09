/**
 * Single source of truth for KPI / number formatting across the dashboard.
 *
 * The API may emit values as raw numbers (preferred) or as legacy pre-formatted
 * strings like `"84h"`, `"1,234"`, `"12.4%"`. Each formatter accepts either —
 * pre-formatted strings get parsed and re-formatted so the surface stays
 * consistent regardless of upstream drift.
 */

/** Coerce raw or pre-formatted input to a finite number, or null if unparseable. */
function toNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const cleaned = String(value).replace(/,/g, '').replace(/\s+/g, '').replace(/[a-zA-Z%]+$/u, '');
  const n = parseFloat(cleaned);
  return Number.isFinite(n) ? n : null;
}

/** `4325` → `"4,325"`, `"1234"` → `"1,234"`. Falls back to the input string on parse failure. */
export function formatCount(value: number | string | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '-');
  return Math.round(n).toLocaleString('en-US');
}

/**
 * Hours formatter. Precision adapts to magnitude:
 *   `253h`     when ≥ 100
 *   `42.8h`    when 10–99.9
 *   `2.8h`     when < 10
 * Accepts raw numbers, `"253 hrs"`, `"84h"`, etc.
 */
export function formatHours(value: number | string | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '-');
  if (n >= 100) return `${Math.round(n)}h`;
  if (n >= 10)  return `${n.toFixed(1)}h`;
  return `${n.toFixed(1)}h`;
}

/** `12.4` or `"12.4"` or `"12.4%"` → `"12.4%"`. */
export function formatPercent(value: number | string | null | undefined, decimals = 1): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '-');
  return `${n.toFixed(decimals)}%`;
}

/** `2.8` → `"2.8"`, with consistent decimal precision. */
export function formatDecimal(value: number | string | null | undefined, decimals = 1): string {
  const n = toNumber(value);
  if (n === null) return String(value ?? '-');
  return n.toFixed(decimals);
}

export type KpiKind = 'count' | 'hours' | 'percent' | 'decimal' | 'text';

/**
 * Parse a warehouse timestamp into a Date. Accepts ISO-8601 (with zone) and
 * naive ClickHouse `YYYY-MM-DD HH:MM:SS[.fff]` strings. The warehouse runs in
 * UTC, so naive strings are UTC wall time — without normalizing, browsers
 * parse them as *local* time and every label shifts by the viewer's offset.
 */
export function parseEventDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  let s = String(value).trim();
  // Date-only: construct at LOCAL midnight, otherwise the ES spec parses it
  // as UTC midnight and viewers west of UTC see the previous calendar day.
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (dateOnly) {
    const d = new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const hasTime = /\d{2}:\d{2}/.test(s);
  const hasZone = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s);
  if (hasTime && !hasZone) s = `${s.replace(' ', 'T')}Z`;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Whole calendar days from today to `d` in the viewer's timezone (signed). */
function calendarDayDiff(d: Date, now: Date): number {
  const a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a.getTime() - b.getTime()) / 86_400_000);
}

/** `Jun 9` this year, `Jun 9 '25` otherwise. */
function formatShortDate(d: Date, now: Date): string {
  const month = d.toLocaleString('en-US', { month: 'short' });
  const sameYear = d.getFullYear() === now.getFullYear();
  return sameYear ? `${month} ${d.getDate()}` : `${month} ${d.getDate()} '${String(d.getFullYear()).slice(-2)}`;
}

/**
 * Compact relative past time, sized for the narrow right column of list rows:
 * `Just now` → `12m ago` → `5h ago` → `Yesterday` → `3d ago` → `Jun 9`.
 */
export function formatTimeAgo(value: string | null | undefined): string {
  const d = parseEventDate(value);
  if (!d) return '-';
  const now = new Date();
  const mins = Math.floor((now.getTime() - d.getTime()) / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const dayDiff = calendarDayDiff(d, now);
  // dayDiff can be 0 with >=24h elapsed on the 25-hour DST fall-back day.
  if (dayDiff === 0) return `${hours}h ago`;
  if (dayDiff === -1) return 'Yesterday';
  if (dayDiff > -7) return `${-dayDiff}d ago`;
  return formatShortDate(d, now);
}

/**
 * Compact relative future time: `Now` → `in 12m` → `in 5h` → `Tomorrow` →
 * `in 3d` → `Jun 21`. Past inputs (stale mock data, clock skew) degrade to
 * `formatTimeAgo` instead of showing a negative delta.
 */
export function formatTimeUntil(value: string | null | undefined): string {
  const d = parseEventDate(value);
  if (!d) return '-';
  const now = new Date();
  const mins = Math.floor((d.getTime() - now.getTime()) / 60_000);
  if (mins < -1) return formatTimeAgo(value);
  if (mins < 1) return 'Now';
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `in ${hours}h`;
  const dayDiff = calendarDayDiff(d, now);
  // dayDiff can be 0 with >=24h remaining on the 25-hour DST fall-back day.
  if (dayDiff === 0) return `in ${hours}h`;
  if (dayDiff === 1) return 'Tomorrow';
  if (dayDiff < 7) return `in ${dayDiff}d`;
  return formatShortDate(d, now);
}

/** Duration in minutes → `45m`, `1h 15m`, `2h`, `1d 3h`. */
export function formatDuration(minutes: number | string | null | undefined): string {
  const n = toNumber(minutes);
  if (n === null || n < 0) return '-';
  const mins = Math.round(n);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hours < 24) return remMins ? `${hours}h ${remMins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours ? `${days}d ${remHours}h` : `${days}d`;
}

/**
 * Compact absolute timestamp for list rows. Adapts to age so it stays short
 * on mobile: today → `14:30`; this year → `Jun 9 · 14:30`; older → `Jun 9 '25`.
 * Falls back to the input string if it cannot be parsed.
 */
export function formatEventTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  const d = parseEventDate(iso);
  if (!d) return String(iso);
  const now = new Date();
  const HH = String(d.getHours()).padStart(2, '0');
  const MM = String(d.getMinutes()).padStart(2, '0');
  const dayDiff = calendarDayDiff(d, now);
  if (dayDiff === 0) return `${HH}:${MM}`;
  // Gate on age, not calendar year, so an hours-old play viewed just after
  // New Year keeps its time instead of degrading to a bare "Dec 31 '25".
  if (dayDiff > -180 || d.getFullYear() === now.getFullYear()) {
    return `${formatShortDate(d, now)} · ${HH}:${MM}`;
  }
  return formatShortDate(d, now);
}

/** Viewer-local part of day for a timestamp: Morning / Afternoon / Evening. */
export function formatTimeOfDay(iso: string | null | undefined): string {
  const d = parseEventDate(iso);
  if (!d) return '';
  const h = d.getHours();
  return h < 12 ? 'Morning' : h < 18 ? 'Afternoon' : 'Evening';
}

/** Polymorphic dispatcher for KPIMetric. */
export function formatKpi(value: number | string | null | undefined, kind: KpiKind): string {
  switch (kind) {
    case 'count':   return formatCount(value);
    case 'hours':   return formatHours(value);
    case 'percent': return formatPercent(value);
    case 'decimal': return formatDecimal(value);
    case 'text':    return value === null || value === undefined ? '-' : String(value);
  }
}
